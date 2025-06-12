import cv2
import numpy as np
import book_memory
from book_memory import BookMemory
from database import book_database
import gradio as gr
import pickle
import types
import sys
from collections import defaultdict
from PIL import Image
from PIL import ImageDraw
from pathlib import Path
import json
import pprint
import copy

# --- stub top-level book_utils ---------------------------------
stub = types.ModuleType("book_utils")
stub.book_database = book_database
stub.WagnerFischer = lambda *a, **kw: None

# --- expose book_memory under the dotted name ------------------
stub.book_memory = book_memory                   # attribute access
sys.modules["book_utils"] = stub                 # top-level
sys.modules["book_utils.book_memory"] = book_memory  # dotted path

# --- unpickle ---------------------------------------------------
with open("fails.pkl", "rb") as fh:
    bm = pickle.load(fh)

print("Loaded OK:", type(bm))

# constants
MANUAL = "Manually label book"
new_bm = BookMemory()            # an "empty" bookmemory for storing final labels
call_to_id = {                    # mapping call_number → its integer id in book_database
    rec["call_number"]: int(k)
    for k, rec in book_database.items()
}

init_state = [0, "u", 0, 0, 0]

# helper functions
def load_image_rgb(idx: int) -> Image.Image:
    """loads and converts a book image from bgr to rgb."""
    bgr = bm.book_img_info[idx]["image"]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

def build_manual_choices():
    """
    return a list of (label, value) tuples for every book in book_database,
    where label = "call_number, alt_title" and value = the database id.
    """
    opts = []
    for db_id, rec in book_database.items():
        callnum   = rec.get("call_number", "")
        alt_title = rec.get("alt_title", "")
        if callnum or alt_title:
            opts.append(f"{callnum}, {alt_title}")
    # always append the manual flag as the last radio option
    opts.append(MANUAL)
    return opts

def annotate_on_image(img, point, radius=30, color=(0, 255, 0, 64), width=2):
    """annotates an image with a point (circle)."""
    img = img.convert("RGBA")

    # make a transparent overlay of the same size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    x, y = point
    r = radius

    # draw a filled ellipse onto the overlay
    draw.ellipse(
        (x - r, y - r, x + r, y + r),
        fill=color,        # semi-transparent fill
        outline=None       # no border (optional)
    )

    # composite overlay onto the base image
    return Image.alpha_composite(img, overlay)

def annotate_skip_box(
    img: Image.Image,
    idx: int,
    outline_color=(255, 0, 0),
    outline_width=10,
):
    """annotates an image with a skip box (rectangle)."""
    base = img.convert("RGBA")
    orig_w, orig_h = base.size

    # extract left/right x from book_positions, cast to int
    left_x  = int(bm.book_positions[idx][0][0])
    right_x = int(bm.book_positions[idx][1][0])

    # create transparent overlay
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # draw only the rectangle outline
    draw.rectangle(
        [(left_x, 0), (right_x, orig_h)],
        outline=outline_color + (255,),
        width=outline_width
    )

    # composite and get combined image
    combined = Image.alpha_composite(base, overlay)
    return combined

def build_radio_options(candidate_ids):
    """
    given bm.book_infos[book_id]['id'] (a list of ints or none),
    return a list of strings of the form "call_number, alt_title".
    skip any none or missing entries. then append the manual option.
    """
    opts = []
    for cid in candidate_ids:
        if cid is None:
            continue
        info = book_database.get(str(cid))
        if not info:
            continue
        callnum   = info.get("call_number", "")
        alt_title = info.get("alt_title", "")
        if callnum or alt_title:
            opts.append(f"{callnum}, {alt_title}")
    # always append the manual flag as the last radio option
    opts.append(MANUAL)
    return opts

def load_text(idx):
    """loads the text associated with a given book id."""
    return str(bm.book_infos[idx]["id"])

# group books by image
img_groups = {}

for idx, info in enumerate(bm.book_infos):
    img_key = id(bm.book_img_info[idx]["image"])
    # initialize: "skipped" starts as a dict mapping each between_indices value → list of idx
    if img_key not in img_groups:
        img_groups[img_key] = {"skipped": {}, "unsure": []}

    if "between_indices" in info:
        bi = info["between_indices"]
        # ensure bi is hashable; if it's a list, convert to tuple
        if isinstance(bi, list):
            bi = tuple(bi)
        img_groups[img_key]["skipped"].setdefault(bi, []).append(idx)
    else:
        img_groups[img_key]["unsure"].append(idx)

# after collecting everything, convert each "skipped" dict -> list of lists
for img_key, buckets in img_groups.items():
    skipped_dict = buckets["skipped"]
    img_groups[img_key]["skipped"] = list(skipped_dict.values())

img_keys = list(img_groups.keys())

# callback functions
def next_entry(state):
    """
    advances the browser to the next book entry based on the current state.
    handles switching between 'unsure' and 'skipped' modes, and iterating through images and book groups.
    returns a tuple of gradio updates and the new state.
    """
    print(f"[debug] next_entry: called with state={state}")
    img_i, fail_mode, u_book_i, s_group_i, s_book_i = state

    if img_i >= len(img_keys):
        print(f"[debug] next_entry: img_i out of range, returning end state")
        return (
            gr.update(),            # image for unsure mode
            gr.update(visible=False),  # radio for unsure mode
            gr.update(visible=False),  # manual dropdown
            gr.update(),            # image for skipped mode
            gr.update(),            # text for skipped mode
            gr.update(visible=False),  # group for unsure mode
            gr.update(visible=False),  # group for skipped mode
            state,
            None # current_display_book_id (none for end state)
        )

    img_key = img_keys[img_i]
    unsure_ids = img_groups[img_key]["unsure"]
    skipped_ids = img_groups[img_key]["skipped"]

    # unsure mode but there are no unsure ids at all, switch to skipped
    if fail_mode == "u" and not unsure_ids:
        print(f"[debug] next_entry: switching to skipped mode")
        return next_entry([img_i, "s", 0, 0, 0])

    if fail_mode == "s" and not skipped_ids:
        print(f"[debug] next_entry: no skipped_ids, advancing to next image")
        return next_entry([img_i + 1, "u", 0, 0, 0])
    
    mode_ids = unsure_ids if fail_mode == "u" else skipped_ids

    if fail_mode == "u":
        if u_book_i >= len(unsure_ids):
            # print(f"[debug] next_entry: all unsure shown, switching to skipped mode")
            return next_entry([img_i, "s", 0, 0, 0])
        book_id = unsure_ids[u_book_i]
    else:  # fail_mode == "s"
        # find between group
        if s_group_i >= len(skipped_ids):
            # print(f"[debug] next_entry: finished sublist, advancing to next image")
            # next image
            return next_entry([img_i + 1, "u", 0, 0, 0])
        current_sublist = skipped_ids[s_group_i]
        # sub list (between) go next
        if s_book_i >= len(current_sublist):
            # print(f"[debug] next_entry: finished this sublist, advancing to next sublist")
            return next_entry([img_i, "s", 0, s_group_i + 1, 0])
        book_id = current_sublist[s_book_i]

    text = load_text(book_id)
    # print(f"[debug] next_entry: fail_mode={fail_mode}, book_id={book_id}, text={text}")

    img = load_image_rgb(book_id)

    next_img_i    = img_i
    next_mode     = fail_mode
    next_u_book_i = u_book_i
    next_s_group  = s_group_i
    next_s_book   = s_book_i

    if fail_mode == "u":
        next_u_book_i += 1
        if next_u_book_i >= len(unsure_ids):
            # we've shown all "unsure" for this image → go to first skipped sublist
            next_mode     = "s"
            next_u_book_i = 0
            next_s_group  = 0
            next_s_book   = 0
    else:  # "s"
        next_s_book += 1
        current_sublist = skipped_ids[s_group_i]
        if next_s_book >= len(current_sublist):
            # finished this sublist → advance to next sublist
            next_s_group += 1
            next_s_book  = 0
            # if that was the last sublist, next call to next_entry will push to next image

    new_state = [next_img_i, next_mode, next_u_book_i, next_s_group, next_s_book]
    print(f"new state: {new_state}")
    if fail_mode == "u":          # unsure layout now active
       # point on book
        point = bm.book_positions[book_id]
        img = annotate_on_image(img, point)
  
        candidate_ids = bm.book_infos[book_id]["id"]
        radio_labels = build_radio_options(candidate_ids)
        radio_update = gr.update(choices=radio_labels, value=None, visible=True)

        # dropdown stays hidden until user picks manual
        manual_update = gr.update(choices=build_manual_choices(),
                                  value=None,
                                  visible=False)
        returned_state = copy.deepcopy(new_state)
        # print(f"[debug] next_entry: returning unsure state: {returned_state}")
        return (
            gr.update(value=img, visible=True), # image for unsure mode
            radio_update,
            manual_update,

            gr.update(visible=False), # image for skipped mode
            gr.update(visible=False),

            gr.update(visible=False),
            gr.update(value="", visible=False),

            gr.update(visible=True),
            gr.update(visible=False),

            returned_state,
            None # current_display_book_id (none for unsure, as we don't need to click it yet)
        )

    else:                    # skipped layout active
        # load the base pil image
        base_img = load_image_rgb(book_id)  # returns rgb → convert in helper
        # overlay skip-box
        img_with_box = annotate_skip_box(base_img, book_id)
        skipped_str = "skipped " + text

        # Get call_number and alt_title for the dynamic label
        print(f"[debug] next_entry: building dynamic label for book_id={book_id}")
        book_info = book_database.get(str(book_id))
        callnum = book_info.get("call_number", "") if book_info else ""
        alt_title = book_info.get("alt_title", "") if book_info else ""
        dynamic_radio_label = f"Is this book {callnum}, {alt_title} in the masked area?"
        print(f"[debug] next_entry: dynamic_radio_label={dynamic_radio_label}")

        returned_state = copy.deepcopy(new_state) # return new_state as current_display_book_id will store the current one.
        # print(f"[debug] next_entry: returning skipped state: {returned_state}")
        return (
            gr.update(visible=False), # hide image for unsure mode
            gr.update(visible=False),
            gr.update(visible=False),

            gr.update(value=img_with_box, visible=True), # show the masked image in img_s
            gr.update(value=skipped_str, visible=True), # show the "skipped {text}" markdown
            gr.update(visible=True, value=None, label=dynamic_radio_label), # show found_radio with dynamic label
            gr.update(value="", visible=True), # clear & show status_skipped

            gr.update(visible=False), # hide group for unsure mode
            gr.update(visible=True), # show group for skipped mode

            returned_state,
            book_id # new: output the book_id of the currently displayed skipped book
        )

def on_radio_change(choice):
    """handles the change event of the radio buttons, toggling manual dropdown visibility."""
    if choice == MANUAL:
        return gr.update(visible=True)
    return gr.update(visible=False)

def on_found_radio(answer, state, current_display_book_id):
    """handles the user's response to whether a book is in the masked area."""
    print(f"[debug] on_found_radio START: answer={answer}, state={state}, current_display_book_id={current_display_book_id}")
    img_i, mode, ub, sg, sb = state

    if answer is None:
        # if no answer is selected (e.g., initial display of cleared radio), do nothing or keep current state
        book_id = current_display_book_id
        base_img = load_image_rgb(book_id)
        img_with_box = annotate_skip_box(base_img, book_id)
        skipped_str  = f"skipped {load_text(book_id)}"

        # Get call_number and alt_title for the dynamic label
        book_info = book_database.get(str(book_id))
        callnum = book_info.get("call_number", "") if book_info else ""
        alt_title = book_info.get("alt_title", "") if book_info else ""
        dynamic_radio_label = f"Is this book {callnum}, {alt_title} in the masked area?"

        return (
            gr.update(value=img_with_box, visible=True), # img_s (should be visible for skipped, not hidden)
            gr.update(visible=True, value=None, label=dynamic_radio_label), # found_radio (visible and cleared with dynamic label)
            gr.update(visible=False), # img_clickable (hidden)
            gr.update(value="", visible=True),  # status_skipped (clear it)
            gr.update(visible=False),  # text_s - NEW
            gr.update(visible=True),                     # grp_skipped
            copy.deepcopy(state),                        # keep the current state
            current_display_book_id                      # pass through current_display_book_id
        )

    if answer == "No":
        book_id = current_display_book_id # use the explicitly displayed book id
        text = load_text(book_id)
        print(f"[debug] on_found_radio: book_id={book_id}, text={text}")
        base = next_entry(state) # this will return the new_state for the next item (11 outputs)
        print(f"[debug] on_found_radio: advancing to next entry, new state={base[-2]}") # adjusted index for new output
        # base outputs: [img_u, radio_u, manual_dd, img_s, text_s, found_radio, status_skipped, grp_unsure, grp_skipped, state, current_display_book_id]
        return (
            base[3],  # image for skipped mode
            base[5],  # radio for skipped mode
            gr.update(visible=False), # image clickable should be hidden if we are advancing
            base[6],  # status for skipped mode
            base[4],  # text for skipped mode
            base[8],  # group for skipped mode
            copy.deepcopy(base[9]),  # state
            base[10]  # current_display_book_id
        )

    # "yes" → show the clickable overlay, use current_display_book_id
    book_id = current_display_book_id # use the explicit current book id
    text = load_text(book_id)
    print(f"[debug] on_found_radio: book_id={book_id}, text={text}")

    base_img     = load_image_rgb(book_id)
    img_with_box = annotate_skip_box(base_img, book_id)
    skipped_str  = f"skipped {text}"

    print(f"[debug] on_found_radio: staying on current entry, state={state}, text={skipped_str}")
    # keep the same state and show interactive elements
    return (
        gr.update(value=img_with_box, visible=False), # hide static image
        gr.update(visible=False),                    # hide found_radio
        gr.update(value=img_with_box, visible=True), # show clickable image
        gr.update(value="Please click on the book location.", visible=True),  # show status message
        gr.update(visible=False),  # text_s - NEW
        gr.update(visible=True),                     # keep group visible
        copy.deepcopy(state),                        # keep the (possibly advanced) main state
        current_display_book_id                      # pass through current_display_book_id
    )

def on_click_book(evt: gr.SelectData, image_component, state):
    """handles clicks on the interactive image, saves the click location, and advances to the next entry."""
    print(f"[debug] on_click_book: evt={evt}, image_component={image_component}, state={state}")
    # unpack the state tuple
    img_i, fail_mode, u_book_i, s_group_i, s_book_i = state

    # find which shelf-photo group we're in
    img_key     = img_keys[img_i]
    skipped_ids = img_groups[img_key]["skipped"]  # a list of lists

    # grab the current sublist and the specific book index
    current_sublist = skipped_ids[s_group_i]
    book_id         = current_sublist[s_book_i]
    text = load_text(book_id)
    print(f"[debug] on_click_book: book_id={book_id}, text={text}")

    # now evt.index gives you (x, y)
    x, y = evt.index
    print(f"[debug] on_click_book: x={x}, y={y}")

    # save that click
    #new_bm.add_book(book_id, x, y)

    # advance to the next entry
    base_updates = next_entry(state)
    print(f"[debug] on_click_book: advancing to next entry, new state={base_updates[-2]}") # adjusted index
    # base_updates is a tuple of 8 component updates + the new state + current_display_book_id

    # return exactly the same number of outputs,
    # clearing any status message as the last update.
    return (
        base_updates[0],           # image for unsure mode
        base_updates[1],           # radio for unsure mode
        base_updates[2],           # manual dropdown
        base_updates[3],           # image for skipped mode
        base_updates[4],           # text for skipped mode
        gr.update(visible=False),  # img_clickable - NEW
        base_updates[7],           # group for unsure mode
        base_updates[8],           # group for skipped mode
        copy.deepcopy(base_updates[9]), # state
        gr.update(value=""),       # status for skipped mode (clear it)
        base_updates[10],           # current_display_book_id
        base_updates[5]            # found_radio - NEW
    )

# gradio ui
CSS = """
#book_choices label span { white-space: pre-wrap; }
body ul.options[role="listbox"] { max-height:220px!important;overflow-y:auto!important;overflow-x:hidden!important;}
"""

with gr.Blocks(title="book browser", css=CSS) as demo:
    gr.Markdown("### Browse Entries")
    state = gr.State(init_state)
    current_display_book_id = gr.State(None) # new state component

    with gr.Group(visible=True) as grp_unsure:
        img_u    = gr.Image(type="pil", height=300, label="")
        radio_u  = gr.Radio(
            choices=[],
            label="Choose one of these matches:",
            visible=False,
            interactive=True,
        )
        manual_dd = gr.Dropdown(
            choices=[],
            label="manual entry:",
            value=None,
            visible=False,
            allow_custom_value=False,
            interactive=True,
        )

        status_u = gr.Markdown(value="", visible=True)   # for warnings

        # whenever the radio value changes, run on_radio_change to toggle manual_dd
        radio_u.change(
            on_radio_change,
            inputs=[radio_u],
            outputs=[manual_dd],
            queue=False
        )

    with gr.Group(visible=False) as grp_skipped:
        # non-interactive "masked" image
        img_s = gr.Image(
            type="pil",
            height=300,
            label="",
            visible=False
        )

        # interactive version (same spot/size), initially hidden
        img_clickable = gr.Image(
            type="pil",
            height=300,
            label="",
            interactive=False, # changed to false
            visible=False
        )

        text_s = gr.Markdown(visible=False)  # Remove the comment about skipped_id

        found_radio = gr.Radio(
            choices=["Yes", "No"],
            label="Is this book in the masked area?",
            visible=False,
            interactive=True,
            value=None # ensure it's not selected by default
        )

        status_skipped = gr.Markdown(value="", visible=True)

        found_radio.change(
            on_found_radio,
            inputs=[found_radio, state, current_display_book_id], # add current_display_book_id
            outputs=[
                img_s,           # show/hide static image
                found_radio,     # show/hide the radio
                img_clickable,   # show/hide interactive image
                status_skipped,  # warning prompt
                text_s,          # "skipped {book_id}" text
                grp_skipped,     # keep group visible
                state,           # keep main state
                current_display_book_id # pass through current_display_book_id, it is not modified here
            ],
            queue=False
        )

        img_clickable.select(
            on_click_book,          # callback(evt, image_component, state)
            inputs=[img_clickable, state],  # pass image component and state
            outputs=[
                img_u, radio_u, manual_dd,
                img_s, text_s, img_clickable,
                grp_unsure, grp_skipped,
                state,              # now only this callback updates state
                status_skipped,
                current_display_book_id, # pass through current_display_book_id, it is updated by next_entry
                found_radio # new output
            ],
            queue=False
        )

    nxt = gr.Button("next →")

    # first load on page render
    demo.load(
        next_entry,
        inputs=[state],
        outputs=[
            img_u,           # image for unsure mode
            radio_u,         # radio for unsure mode
            manual_dd,       # manual dropdown

            img_s,           # image for skipped mode
            text_s,          # text for skipped mode

            found_radio,     # found radio
            status_skipped,  # status for skipped mode

            grp_unsure,      # group for unsure mode
            grp_skipped,     # group for skipped mode

            state,           # state
            current_display_book_id # new output
        ],
        queue=False
    )

    # subsequent clicks
    nxt.click(
        next_entry,
        inputs=[state],
        outputs=[
            img_u,           # image for unsure mode
            radio_u,         # radio for unsure mode
            manual_dd,       # manual dropdown

            img_s,           # image for skipped mode
            text_s,          # text for skipped mode

            found_radio,     # found radio
            status_skipped,  # status for skipped mode

            grp_unsure,      # group for unsure mode
            grp_skipped,     # group for skipped mode

            state,           # state
            current_display_book_id # new output
        ],
    )

if __name__ == "__main__":
    demo.launch() 
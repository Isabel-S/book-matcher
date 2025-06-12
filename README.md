# Book Matcher
## TODO
- saving the labels and locations into a new book memory object
- after labelling the skipped image, implement asking if there are any other books in the masked bbox area
- allow labeller to skip labeling this image or go back
- keyboard commands
- for skipped books, update the title and call ID on the screen

## Goal Functionality

- **For each image** in book memory:
  - Find all books associated with that image.
  - **Unsure-labeled books** (≥ 2 possible labels):
    - Draw the book’s `bbox` on the image.
    - For each unsure book:
      - Present its possible labels as radio buttons, plus a **Manual** option that opens the dropdown.
      - Save the user’s selection back into book memory.
  - **Skipped books** (the remaining books):
    - Sort by `between_indices` (ascending).
    - Group entries that share the same `between_indices`.
    - For each group of skipped books:
      - Generate a masked image by taking the `bbox` of the lowest and highest seen indices and masking everything outside their span.
      - **Iterate** over each skipped index in order:
        1. Ask:  
           > “Is this *(`id` and `alt_title`)* in the masked area?”  
        2. If **yes**:
           - Prompt **“Click on it.”**
           - Record the click location and save it in book memory.
        3. If **no**:
           - Move on to the next skipped book.
      - After processing the group:
        - Ask:  
          > “Are there any other books in the image that are not these: [list of books labeled “yes”]?”
        - If **yes**:
          - Prompt **“Click on it.”**
          - Open the manual dropdown for entry and save in book memory.
          - Repeat “Are there any other books…?” until the user says **no**.
        - If **no**:
          - Proceed to the next `between_indices` group (if any).
- **At the end**, show a **Submit** button (no review step for now).

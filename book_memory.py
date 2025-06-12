import numpy as np
import sys 
import os 

# import Levenshtein

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.spatial.transform import Rotation as R

sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), 'book_utils'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# from robot import project_book_on_cam_vec, get_hand_cam_extrinsics
from database import book_database

class BookMemory:
    def __init__(self, database=book_database):
        self.book_positions = []  # list of np.array([x, y, z]). For skipped book fails, this is a list of the two points between which the book was skipped
        self.book_infos = []  # same-length list of book data (e.g., {"id": ..., "similarity": ..., "confidence": ...})
        self.book_img_info = [] # only for fails, same-length list (e.g. {"image": [bgr, depth], "cam_extr": ..., "mask": ...})

        self.out_of_view_thresh = 0.8
        self.window = [] # assumes we are moving generally left to right, indices in self.book_positions to look at
        self.book_database = database
        self._recent_indices = []  # Track indices of recently added books

    def __len__(self):
        return len(self.book_positions)

    def resort_within_indices(self, indices):
        window_positions = np.array(self.book_positions)[np.array(indices)]
        sorted_within_window = np.argsort(window_positions[:, 0])
        return sorted_within_window

    def add_book(self, position, info, img_info=None):
        """
        Add a book to memory.
        
        Args:
            position: 3D position of the book
            info: Dictionary containing book information (id, similarity, etc.)
            img_info: Optional dictionary containing image information
            
        Returns:
            int: Index of the added book, or None if book was not added
        """
        # Check if we already have this book
        for i, book in enumerate(self.book_infos):
            if book['id'] == info['id']:
                # Update existing book
                self.book_positions[i] = position
                self.book_infos[i].update(info)
                if img_info:
                    self.book_img_info[i] = img_info
                self._recent_indices.append(i)
                return i
        
        # Add new book
        self.book_positions.append(position)
        info["nearby_window"] = self.window[:-1] # last element should always be the current index
        self.book_infos.append(info)
        if img_info is not None:
            self.book_img_info.append(img_info)
        new_index = len(self.book_positions) - 1
        self._recent_indices.append(new_index)
        return new_index

    def get_recent_indices(self):
        """
        Get the indices of recently added books.
        
        Returns:
            list: List of indices of recently added books
        """
        recent = self._recent_indices.copy()
        self._recent_indices = []  # Clear the recent indices after getting them
        return recent

    def get_book(self, idx):
        if isinstance(idx, list) or isinstance(idx, np.ndarray):
            positions = [self.book_positions[i] for i in idx]
            infos = [self.book_infos[i] for i in idx]
            return positions, infos
        else:
            return self.book_positions[idx], self.book_infos[idx]

    def plot_book_positions(self, indices=None, cam_position=None, robot_position=None):
        positions = np.array(self.book_positions)
        if indices is not None:
            positions = positions[np.array(indices)]
        else:
            indices = list(range(len(positions)))

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        ax.scatter(positions[:, 0], positions[:, 1], positions[:, 2], c='b', marker='o')

        for i, pos in zip(indices, positions):
            ax.text(pos[0], pos[1], pos[2], str(i), fontsize=9, color='red')
        
        if robot_position is not None:
            cam_position = get_hand_cam_extrinsics(robot_position)["extrinsics"]["hand_camera"]

        if cam_position is not None:
            cam_pos = cam_position[:3]
            cam_rpy = cam_position[3:]  # roll, pitch, yaw
            # Plot camera position
            ax.scatter(cam_pos[0], cam_pos[1], cam_pos[2], c='g', marker='^', s=100)
            ax.text(cam_pos[0], cam_pos[1], cam_pos[2], 'orig_cam', fontsize=10, color='green')

            # Optional: show orientation vector (just a simple directional arrow)
            direction = np.array([np.cos(cam_rpy[2]), np.sin(cam_rpy[2]), 0.0])  # assume flat yaw
            ax.quiver(cam_pos[0], cam_pos[1], cam_pos[2],
                    direction[0], direction[1], direction[2],
                    length=0.05, color='green', normalize=True)

        plt.show()

def load_from_file(filepath):
    import pickle
    with open(filepath, 'rb') as f:
        return pickle.load(f)


if __name__ == "__main__":
    bm = load_from_file(os.path.join(os.path.dirname(__file__), "..", "found_books.pkl"))
    print("Found books:", len(bm))
    print(bm.book_infos)   

    fails = load_from_file(os.path.join(os.path.dirname(__file__), "..", "fails.pkl"))
    print("Fails:", len(fails))
    print("fails.book_infos:", fails.book_infos)
    print("fails.book_positions:", fails.book_positions)
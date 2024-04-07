import os
from pathlib import Path

import numpy as np
import pandas as pd
from deepface import DeepFace
from sklearn.metrics import confusion_matrix, roc_curve
from tqdm.autonotebook import tqdm
import matplotlib.pyplot as plt
from typing import Tuple

"""
Current database format
data/
    database/
            authorized_users/
                            /1
                                img1.jpg
                                img2.jpg
                            ...
                            /100
                                img1.jpg
                                img2.jpg
            incoming_users/
                            authorized_users/
                                            /1
                                                img1.jpg
                                                img2.jpg
                                            ...
                                            /50
                                                img1.jpg
                                                img2.jpg
                            unauthorized_users/
                                            /101
                                                img1.jpg
                                                img2.jpg
                                            ...
                                            /150
                                                img1.jpg
                                                img2.jpg
"""


class VerificationSystem:
    def __init__(self, database_path: str, acceptance_threshold: float = 0.5):
        self.database_path = database_path
        self.acceptance_threshold = acceptance_threshold

        self.initialize_database()

    def initialize_database(self) -> None:
        DeepFace.find(
            img_path=self.get_incoming_authorized_user_path(),
            db_path=os.path.join(self.database_path, "authorized_users"),
            threshold=self.acceptance_threshold,
            enforce_detection=False,
        )

    def verify_user(
        self, user_name: str, user_photo_path: str | np.ndarray
    ) -> Tuple[bool, float]:
        # TODO: change it in UI, now function return Tuple!
        faces_found = DeepFace.find(
            img_path=user_photo_path,
            db_path=os.path.join(self.database_path, "authorized_users"),
            threshold=self.acceptance_threshold,
            enforce_detection=False,
            silent=True,
        )

        # no face detected or above acceptance threshold
        if faces_found[0].empty:
            return False, np.inf

        # TODO: find a way to make it path independent
        # assumption that only one face is in the image
        predicted_user_name = faces_found[0]["identity"].apply(
            lambda x: Path(x).parts[3]
        )[
            0
        ]  # get the distance closest match

        is_access_granted = user_name == predicted_user_name

        return is_access_granted, faces_found[0]["distance"]

    def verify_multiple_users(self, incoming_users_path: str) -> pd.DataFrame:
        df_users = pd.DataFrame(columns=["image_path", "is_access_granted", "distance"])

        for user_name in tqdm(
            iterable=os.listdir(incoming_users_path), desc="Processing users"
        ):
            for user_photo in tqdm(
                iterable=os.listdir(os.path.join(incoming_users_path, user_name)),
                desc="Processing user photos",
                leave=False,
            ):
                is_access_granted, distance = self.verify_user(
                    user_name=user_name,
                    user_photo_path=os.path.join(
                        incoming_users_path, user_name, user_photo
                    ),
                )

                df_user = pd.DataFrame(
                    {
                        "image_path": os.path.join(
                            incoming_users_path, user_name, user_photo
                        ),
                        "is_access_granted": is_access_granted,
                        "distance": distance,
                    },
                    index=[0],
                )

                df_users = pd.concat([df_users, df_user], ignore_index=True)

        return df_users

    @staticmethod
    def calculate_access_granted_rate(
        df_users: pd.DataFrame,
    ) -> float:
        return df_users["is_access_granted"].sum() / len(df_users)

    @staticmethod
    def draw_ROC_curve(
        df_users_authorized: pd.DataFrame, df_users_unauthorized: pd.DataFrame
    ) -> Tuple[int, int, int, int]:
        """
        Function to draw ROC curve based on DFs with authorized and unauthorized users, based on changing threshold
        of distance.
        :param df_users_authorized: DF with users in database
        :param df_users_unauthorized: DF with users that are not authorized in database
        :return: Tuple of TN, FP, FN, TP
        """
        df_concatenated = pd.concat(
            [df_users_authorized, df_users_unauthorized], axis=0
        )
        true_labels = [True] * len(df_users_authorized) + [False] * len(
            df_users_unauthorized
        )
        predicted_labels = df_concatenated["is_access_granted"].to_list()
        distances = df_concatenated["distance"]
        distances = np.where(
            np.isinf(distances), verification_system.acceptance_threshold, distances
        )  # change np.inf value to distance == acceptance threshold

        fpr, tpr, thresholds = roc_curve(true_labels, distances)
        plt.figure()
        plt.plot(fpr, tpr)
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("ROC Curve")
        plt.show()

        tn, fp, fn, tp = confusion_matrix(
            y_true=true_labels, y_pred=predicted_labels
        ).ravel()
        return tn, fp, fn, tp

    @staticmethod
    def calculate_far_frr(
        df_users_authorized: pd.DataFrame, df_users_unauthorized: pd.DataFrame
    ) -> Tuple[float, float]:
        """
        Function to calculate False Acceptance Rate, False Rejection Rate

        :param df_users_authorized: DF with users in database
        :param df_users_unauthorized: DF with users that are not authorized in database
        :return: False Acceptance Rate, False Rejection Rate
        """
        df_concatenated = pd.concat(
            [df_users_authorized, df_users_unauthorized], axis=0
        )
        true_labels = [True] * len(df_users_authorized) + [False] * len(
            df_users_unauthorized
        )
        predicted_labels = df_concatenated["is_access_granted"].to_list()
        tn, fp, fn, tp = confusion_matrix(
            y_true=true_labels, y_pred=predicted_labels
        ).ravel()

        tpr = tp / (tp + fn)
        fpr = fp / (fp + tn)
        far = 1 - tpr
        frr = fpr
        return far, frr

    def get_incoming_authorized_user_path(self) -> str:
        return os.path.join(
            self.database_path, "incoming_users", "authorized_users", "1", "000023.jpg"
        )

    def get_incoming_unauthorized_user_path(self):
        return os.path.join(
            self.database_path,
            "incoming_users",
            "unauthorized_users",
            "101",
            "020633.jpg",
        )

    def get_problematic_incoming_authorized_user_path(self):
        return os.path.join(
            self.database_path, "incoming_users", "authorized_users", "22", "001677.jpg"
        )

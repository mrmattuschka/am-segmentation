from collections import defaultdict
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
from torch.utils.data import Dataset
import albumentations as albu
from albumentations.pytorch.transforms import img_to_tensor
import cv2


def make_image_mask_dfs(data_path):
    image_paths = defaultdict(list)
    for group_path in data_path.iterdir():
        # print(f'{group_path.name} group images collecting')
        for image_path in sorted((group_path / 'source').glob('*.png')):
            mask_path = group_path / 'mask' / image_path.name

            image_paths['source'].append((group_path.name, image_path))
            image_paths['mask'].append((group_path.name, mask_path))

    image_df = pd.DataFrame(image_paths['source'], columns=['group', 'path'])
    mask_df = pd.DataFrame(image_paths['mask'], columns=['group', 'path'])

    return image_df, mask_df


def default_transform(p=1):
    return albu.Compose([
        albu.Normalize(p=1)
    ], p=p)


def train_transform(p=1):
    return albu.Compose([
        albu.VerticalFlip(p=0.5),
        albu.HorizontalFlip(p=0.5),
        albu.Transpose(p=0.5),
        albu.RandomRotate90(p=0.5),
        albu.ShiftScaleRotate(p=1),
        albu.IAAAdditiveGaussianNoise(p=0.5, scale=(0, 0.02 * 255)),
        albu.OneOf([
            albu.CLAHE(p=1, clip_limit=3),
            albu.RandomBrightnessContrast(p=1, brightness_limit=0.2, contrast_limit=0.2),
            albu.RandomGamma(p=1, gamma_limit=(80, 120)),
        ], p=1),
        albu.Normalize(p=1),
    ], p=p)


def valid_transform(p=1):
    return albu.Compose([
        albu.Normalize(p=1),
    ], p=p)


class AMDataset(Dataset):
    def __init__(self, image_df, mask_df, transform=None):
        self.transform = transform
        self.image_df = image_df
        self.mask_df = mask_df

    def __len__(self):
        return len(self.mask_df)

    def __getitem__(self, idx):
        image_path = self.image_df.iloc[idx].path
        image = cv2.imread(str(image_path))
        mask_path = self.mask_df.iloc[idx].path
        if mask_path.exists():
            mask = cv2.imread(str(mask_path))[:, :, :1].astype(np.float32)
        else:
            image_shape = image.shape[-2:]
            mask = np.zeros((1,) + image_shape)

        if self.transform:
            augmented = self.transform(image=image, mask=mask)
            image = augmented['image']
            mask = augmented['mask']

        image = img_to_tensor(image)
        mask = img_to_tensor(mask)
        return image, mask

    def __add__(self, other):
        comb_image_df = pd.concat([self.image_df, other.image_df])
        comb_mask_df = pd.concat([self.mask_df, other.mask_df])
        return AMDataset(comb_image_df, comb_mask_df, self.transform)


def load_ds(data_path, transform, groups=None, size=None):
    image_df, mask_df = make_image_mask_dfs(Path(data_path))
    if groups:
        image_df = image_df[image_df.group.isin(groups)]
        mask_df = mask_df[mask_df.group.isin(groups)]

    if size:
        n = image_df.shape[0]
        if n < size:
            mult = ceil(size / n)
            image_df = pd.concat([image_df] * mult).head(size)
            mask_df = pd.concat([mask_df] * mult).head(size)
        else:
            image_df = image_df.head(size)
            mask_df = mask_df.head(size)

    return AMDataset(image_df, mask_df, transform=transform)
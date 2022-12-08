import os
import glob
import argparse
from omegaconf import OmegaConf
import collections
import pandas as pd
import numpy as np
import tqdm
from pathlib import Path

import pytorch_lightning as pl
import torch

from data.dataset import NLST_2D_NIFTI_Dataset, NLST_NIFTI_Dataset
from data.dataset import data_to_slices
from models.training_modules import binary_dice_coefficient
from utils.utils import get_model

from matplotlib.pyplot import figure, imshow, axis, savefig
import matplotlib.pyplot as plt


def showImagesHorizontally(list_of_arrs):
    fig = figure()
    num_files = len(list_of_arrs)
    for i in range(num_files):
        a = fig.add_subplot(1, num_files, i+1)
        image = list_of_arrs[i]
        imshow(image, cmap='Greys_r')
        if i == 0:
            title = 'scan'
        elif i == 1:
            title = 'mask'
        else:
            title ='prediction'
        a.set_title(title)
        axis('off')
        plt.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser(description='Processing configuration for training')
    parser.add_argument('--exp_path', type=str, help='path to experiment path',
                        default='/home/mdo4009/transplant-rejection/logs/UNet-2D/UNet__2022-12-03-11-37-40/')
    parser.add_argument('--save_fig', type=bool, help='save prediction figure', default=False)
    args = parser.parse_args()

    pl.seed_everything(int(os.environ.get('LOCAL_RANK', 0)))

    # Load configuration file
    config_path = os.path.join(args.exp_path, 'config.yaml')
    config = OmegaConf.load(config_path)

    raw_directory = config['data']['raw_directory']
    annotations_dir = config['data']['annotations_dir']

    data_dict = {}
    for raw_sample in glob.glob(raw_directory + '**'):
        sample_id = raw_sample.split('/')[-1][:-4]
        for label_path in glob.glob(annotations_dir + '**'):
            if sample_id in label_path and '.nii' in label_path:
                data_dict.update({raw_sample: label_path})

    # Data split
    splits = pd.read_csv(config['data']['data_splits'])

    data_dict_val = {}
    for index, row in splits.iterrows():
        patient_id = row['id']
        split = row['set']

        for key in data_dict.keys():
            if str(patient_id) in key and split == 'val':
                data_dict_val.update({key: data_dict[key]})

    if len(config['data']['target_size']) == 2:
        data_val = data_to_slices(collections.OrderedDict(data_dict_val), nifti=True)

        val_dataset = NLST_2D_NIFTI_Dataset(
            patients_paths=data_val,
            target_size=config['data']['target_size'],
            transform=None
        )
    else:
        val_dataset = NLST_NIFTI_Dataset(
            patients_paths=data_dict_val,
            target_size=config['data']['target_size'],
            transform=None
        )

    # Init model
    model = get_model(config['model']['name'], spatial_dims=len(config['data']['target_size']))

    # Load weights
    all_checkpoints = [str(x) for x in sorted(Path(args.exp_path).iterdir(), key=os.path.getmtime) if '.ckpt' in str(x)]
    checkpoint_path = all_checkpoints[-1]
    state_dict = torch.load(str(checkpoint_path), map_location='cpu')['state_dict']
    for key in list(state_dict.keys()):
        state_dict[key.replace('net.', '')] = state_dict.pop(key)

    model.load_state_dict(state_dict)
    model.eval()

    dice_scores = []
    for vis_id in tqdm.tqdm(range(len(val_dataset))):
        img_ex = val_dataset[vis_id]
        img, mask = torch.unsqueeze(img_ex['data'], 0), img_ex['label'].squeeze()

        prediction = model(img).squeeze().detach()
        sigmoid_pred = torch.sigmoid(prediction)
        class_pred = torch.round(sigmoid_pred)

        dice_coeff = binary_dice_coefficient(class_pred, mask)
        dice_scores.append(dice_coeff)

        if args.save_fig:
            f = showImagesHorizontally([img.squeeze().numpy(), mask.numpy(), class_pred.numpy()])
            savefig('result_{}.png'.format(vis_id), bbox_inches='tight')

    print('Mean Dice on val: {}'.format(np.mean(dice_scores)))


if __name__ == '__main__':
    main()

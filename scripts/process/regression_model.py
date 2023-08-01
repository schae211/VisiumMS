"""
Script to generate a regression model for cell2location from raw sn-seq data
"""

# usage
# python scripts/process/regression_model.py --output cellbender
# python scripts/process/regression_model.py --output cellranger

import sys
import scanpy as sc
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from pathlib import Path
import re

# this line forces theano to use the GPU and should go before importing cell2location
os.environ["THEANO_FLAGS"] = 'device=cuda0,floatX=float32,force_device=True'

import cell2location
import scvi

from cell2location.utils.filtering import filter_genes
from cell2location.models import RegressionModel

import argparse

# TODO: harcoded configs
label_name = "cell_types"
sample_id = "sample_id"
recompute = True
min_cells_per_type = 20

# add command line flag arguments to specify either "cellbender" or "cellranger" output
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=str, required=True)
args = parser.parse_args()

# set up relative paths within the project
current_folder = Path(__file__).parent
# current_folder = globals()['_dh'][0]
if args.output == "cellbender":
    # NOTE: Updated cellranger atlas from Celia on 04.07: "annotated_cellbender_mod.h5ad"
    adata_annotated = sc.read_h5ad(current_folder / ".." / ".." / "data" / "prc" / "sc" / "annotated_cellbender_mod.h5ad")
    raw_input_dir = current_folder / ".." / ".." / "data" / "prc" / "sc" / "cellbender"
    samples = [sample for sample in os.listdir(raw_input_dir) if not sample.startswith(".")]
    adata_objects = {}
    for sample in samples:
        adata = sc.read_10x_h5(raw_input_dir / sample / "cell_bender_matrix_filtered.h5")
        adata.var_names_make_unique()
        adata.obs_names = [f"{sample}_{cell}" for cell in adata.obs_names]
        adata_objects[sample] = adata
    adata_raw = sc.concat(list(adata_objects.values()), join="outer", label=sample_id, keys=list(adata_objects.keys()))
    del adata_objects
    output_dir = current_folder / ".." / ".." / "data" / "prc" / "sc" / "c2l_model" / "cellbender"

elif args.output == "cellranger":
    # NOTE: Updated cellranger atlas from Celia on 13.06: "annotated_cellranger.h5ad"
    adata_annotated = sc.read_h5ad(current_folder / ".." / ".." / "data" / "prc" / "sc" / "annotated_cellranger.h5ad")
    raw_input_dir = current_folder / ".." / ".." / "data" / "raw" / "sc"
    samples = [sample for sample in os.listdir(raw_input_dir) if not sample.startswith(".")]
    adata_objects = {}
    for sample in samples:
        adata = sc.read_10x_h5(raw_input_dir / sample / "filtered_feature_bc_matrix.h5")
        adata.var_names_make_unique()
        adata.obs_names = [f"{sample}_{cell}" for cell in adata.obs_names]
        adata_objects[sample] = adata
    adata_raw = sc.concat(list(adata_objects.values()), join="outer", label=sample_id, keys=list(adata_objects.keys()))
    del adata_objects
    output_dir = current_folder / ".." / ".." / "data" / "prc" / "sc" / "c2l_model" / "cellranger"

else:
    raise ValueError("output must be either 'cellbender' or 'cellranger'")
output_dir.mkdir(parents=True, exist_ok=True)

# check
adata_annotated.obs_names = [f"{sample}_{re.sub('-[0-9]+$', '', cell)}" for sample, cell in zip(adata_annotated.obs[sample_id], adata_annotated.obs_names)]
print(adata_annotated.obs_names[:6])
print(adata_annotated.obs_names[-6:])

# check
print(adata_raw.obs_names[:6])
print(adata_raw.obs_names[-6:])

# check whether the annotated adata is a subset of the raw adata
assert set(adata_annotated.obs_names).issubset(set(adata_raw.obs_names)), "The annotated adata is not a subset of the raw adata"

sample_meta = pd.read_excel(current_folder / ".." / ".." / "data" / "Metadata_all.xlsx", sheet_name="snRNA-seq")

cond_dict = {
    "All": sample_meta.sample_id,
    "MS": sample_meta.sample_id[sample_meta.Condition=="MS"],
    "Control": sample_meta.sample_id[sample_meta.Condition=="Control"],
    "CA": sample_meta.sample_id[sample_meta.lesion_type=="CA"],
    "CI": sample_meta.sample_id[sample_meta.lesion_type=="CI"],
    "A": sample_meta.sample_id[sample_meta.lesion_type=="A"],
}
print(cond_dict)

assert set(sample_meta.sample_id) == set(adata_raw.obs[sample_id]), "Samples are missing from the raw adata"
assert set(sample_meta.sample_id) == set(adata_annotated.obs[sample_id]), "Samples are missing from the annotated adata"

# transfer the annotation
adata_raw = adata_raw[adata_annotated.obs_names, :]
adata_raw.obs = adata_annotated.obs.copy()

# save the raw adata object to run DOT
if args.output == "cellbender":
    adata_raw.write(current_folder / ".." / ".." / "data" / "prc" / "sc" / "adata_raw_cellbender.h5ad")
elif args.output == "cellranger":
    adata_raw.write(current_folder / ".." / ".." / "data" / "prc" / "sc" / "adata_raw_cellranger.h5ad")

# Run one model for each spec
for condition, samples in cond_dict.items():

    print(condition)
    adata = adata_raw[adata_raw.obs[sample_id].isin(samples), :].copy()
    print(adata)
    print(adata.obs.sample_id.unique())

    # remove cell types with fewer than min_cells_per_type
    cell_counts = adata.obs[label_name].value_counts()
    print(cell_counts)
    labels_to_remove = cell_counts[cell_counts < min_cells_per_type].index.to_list()
    print(f"Removing:\n{labels_to_remove}")
    adata = adata[~adata.obs[label_name].isin(labels_to_remove), :].copy()
    print(adata)

    tmp_out = output_dir / (condition + "_reg_model")
    tmp_out.mkdir(parents=True, exist_ok=True)

    # check whether the regression model should be recomputed
    if (not recompute) and (tmp_out / "inf_aver.csv").exists():
        print(f"Found existing results in {tmp_out}, skipping")
        continue
    print(f"Running regression model for {condition}, saving in {tmp_out}")

    # Filter by cell2loc thresholds
    selected = filter_genes(adata, cell_count_cutoff=5, cell_percentage_cutoff2=0.03, nonz_mean_cutoff=1.12)
    adata = adata[:, selected].copy()

    # use integer encdoing for sample and celltype covariates (scvi utility)
    cell2location.models.RegressionModel.setup_anndata(adata=adata,
                                                       # 10X reaction / sample / batch
                                                       batch_key=sample_id,
                                                       # cell type, covariate used for constructing signatures
                                                       labels_key=label_name
    )

    # Run regression model
    # See https://github.com/BayraktarLab/cell2location/blob/a583a836b3a932ac6b4de54edd56b8dcf235245a/cell2location/models/reference/_reference_module.py#L13
    mod = RegressionModel(adata)
    mod.view_anndata_setup()

    # Training 
    mod.train(max_epochs=250,  # 
              batch_size=2500, # default
              train_size=1,    # use full training set
              lr=0.002,        # default learning rate for ClippedAdam optimizer
              use_gpu=True)

    # Save training plot
    fig, ax = plt.subplots(1,1, facecolor='white')
    mod.plot_history(20, ax=ax)
    fig.savefig(tmp_out / "training_plot.png", dpi=300, bbox_inches='tight')

    # In this section, we export the estimated cell abundance (summary of the posterior distribution).
    adata = mod.export_posterior(
        adata, sample_kwargs={'num_samples': 1000, 'batch_size': 2500, 'use_gpu': True}
    )
    
    # TODO: Should we save the model as well?
    mod.save(str(tmp_out / "c2l_mod"), overwrite=True)
    adata.write(tmp_out / "sc.h5ad")

    # export estimated expression in each cluster
    if 'means_per_cluster_mu_fg' in adata.varm.keys():
        inf_aver = adata.varm['means_per_cluster_mu_fg'][[f'means_per_cluster_mu_fg_{i}'
                                        for i in adata.uns['mod']['factor_names']]].copy()
    else:
        inf_aver = adata.var[[f'means_per_cluster_mu_fg_{i}'
                                        for i in adata_raw.uns['mod']['factor_names']]].copy()
    inf_aver.columns = adata.uns['mod']['factor_names']

    inf_aver.to_csv(tmp_out / "inf_aver.csv")

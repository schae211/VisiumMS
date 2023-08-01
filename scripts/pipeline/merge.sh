echo '## Merging of samples ##'
<<<<<<< HEAD
python scripts/process/merge.py --output cellbender
python scripts/process/merge.py --output cellranger
python scripts/plot/merge_metrics.py --output cellbender
python scripts/plot/merge_metrics.py --output cellranger
=======
python scripts/process/merge.py -i data/prc/sc/ -m data/metadata.csv  -o data/prc/sc/
python scripts/plot/merge_metrics.py -i data/prc/sc/merged.h5ad -o figures/
>>>>>>> 4059a4c8e2af9c39af787ebee1439fc854d311d6

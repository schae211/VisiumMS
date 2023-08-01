echo '## Integration of samples ##'
<<<<<<< HEAD
python scripts/process/integrate.py --output cellbender
python scripts/process/integrate.py --output cellranger
python scripts/plot/integrate_metrics.py --output cellbender
python scripts/plot/integrate_metrics.py --output cellranger
=======
python scripts/process/integrate.py -i data/prc/sc/merged.h5ad -o data/prc/sc/
python scripts/plot/integrate_metrics.py -i data/prc/sc/integrated.h5ad -o figures
>>>>>>> 4059a4c8e2af9c39af787ebee1439fc854d311d6

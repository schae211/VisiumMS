echo '## QC ##'
<<<<<<< HEAD
python scripts/process/qc.py --output cellbender
python scripts/process/qc.py --output cellranger
python scripts/plot/qc_metrics.py --output cellbender
python scripts/plot/qc_metrics.py --output cellranger
=======
python scripts/process/qc.py -i data/raw/sc/ -o data/prc/sc/
python scripts/plot/qc_metrics.py -i data/prc/sc/ -o figures/
>>>>>>> 4059a4c8e2af9c39af787ebee1439fc854d311d6

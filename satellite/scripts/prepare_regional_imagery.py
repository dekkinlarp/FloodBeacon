"""Build Git-sized dated regional imagery; requires the processing dependency group."""
from pathlib import Path
from floodbeacon.regional_imagery import prepare_region

if __name__ == '__main__':
    prepare_region(Path(__file__).resolve().parents[1] / 'data/research/ahr-regional')

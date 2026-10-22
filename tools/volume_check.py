import sys
from pathlib import Path

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))
sys.stdout = (project / "artifacts/volumes.log").open("w", buffering=1)
sys.stderr = sys.stdout

from smallthings.ntfs import Volume, Windows

for root, identity in Windows().volumes():
    print("Opening", root, flush=True)
    volume = Volume(root, identity)
    print(root, "sector", volume.sector_size, "cluster", volume.cluster_size,
          "record", volume.record_size, "MFT bytes", volume.mft_length,
          "journal", volume.journal_position(), flush=True)
    volume.close()

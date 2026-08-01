import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from src.monitor import *

if __name__ == "__main__":
    main()

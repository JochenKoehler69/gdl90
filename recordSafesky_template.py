__gdl90_master_path__ = "path-to-gdl90-master-lib"

import sys
sys.path.append(__gdl90_master_path__)
print(sys.path)

import gdl90_recorder

gdl90_recorder("-p 4000")


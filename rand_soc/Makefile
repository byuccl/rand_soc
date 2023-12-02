IN_ENV = . .venv/bin/activate &&

run: .venv/bin/activate
	$(IN_ENV) python main.py ./temp --seed 0

vivado:
	cd temp/ && /tools/Xilinx/Vivado/2022.2/bin/vivado -source design.tcl

env: .venv/bin/activate

.venv/bin/activate: ../requirements.txt
	python3 -m venv .venv
	$(IN_ENV) cd ../ &&  pip install -r requirements.txt

.PHONY: env run all
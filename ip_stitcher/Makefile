IN_ENV = . .venv/bin/activate &&

run: .venv/bin/activate
	$(IN_ENV) python main.py

vivado:
	cd designs/design_0 && /tools/Xilinx/Vivado/2022.2/bin/vivado -source design.tcl

env: .venv/bin/activate

.venv/bin/activate: requirements.txt
	python3 -m venv .venv
	$(IN_ENV) pip install -r requirements.txt

.PHONY: env run all
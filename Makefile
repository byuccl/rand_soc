IN_ENV = . .venv/bin/activate &&

run: .venv/bin/activate
	$(IN_ENV) python main.py ./temp default_config.yaml --seed 0 --part xc7a200tlffv1156-2L

vivado:
	cd temp/ && /tools/Xilinx/Vivado/2022.2/bin/vivado -source design.tcl

env: .venv/bin/activate
cleanenv:
	rm -rf .venv

.venv/bin/activate: requirements.txt
	python3 -m venv .venv
	$(IN_ENV) pip install -r requirements.txt

.PHONY: env run all vivado cleanenv
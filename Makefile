IN_ENV = . .venv/bin/activate &&

run: .venv/bin/activate
	$(IN_ENV) python main.py ./temp default_config.yaml --seed 0 --part xc7a200tlffv1156-2L

vivado:
	cd temp/ && /tools/Xilinx/Vivado/2024.2/bin/vivado -source design.tcl

# Quick first-pass test: build many random designs through Tcl creation only
# (no Vivado). Override count with N=, e.g. `make smoke N=50`.
N ?= 30
smoke: .venv/bin/activate
	$(IN_ENV) python smoke_test.py -n $(N) --part xc7a200tlffv1156-2L

env: .venv/bin/activate
cleanenv:
	rm -rf .venv

.venv/bin/activate: requirements.txt
	python3 -m venv .venv
	$(IN_ENV) pip install -r requirements.txt

.PHONY: env run all vivado cleanenv smoke
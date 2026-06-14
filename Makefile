IN_ENV = . .venv/bin/activate &&
VIVADO = /tools/Xilinx/Vivado/2024.2/bin/vivado
PART = xc7a200tlffv1156-2L
SEED = 0
# Creator config. Override to test other IP sets, e.g.
# `make vivado-test CONFIG=fft_config.yaml N=50`.
CONFIG ?= default_config.yaml

run: .venv/bin/activate
	$(IN_ENV) python main.py ./temp $(CONFIG) --seed $(SEED) --part $(PART)

# Generate a design whose Tcl stops after block-design creation/validation
# (no synthesis).
run-bd: .venv/bin/activate
	$(IN_ENV) python main.py ./temp $(CONFIG) --seed $(SEED) --part $(PART) --no-synth

vivado:
	cd temp/ && $(VIVADO) -source design.tcl

# Build a design and run it through Vivado only up to block-design validation
# (no synthesis) -- a fast check that the generated design is actually valid.
vivado-bd: run-bd
	cd temp/ && $(VIVADO) -source design.tcl

# Quick first-pass test: build many random designs through Tcl creation only
# (no Vivado). Override count with N=, e.g. `make smoke N=50`.
N ?= 30
smoke: .venv/bin/activate
	$(IN_ENV) python smoke_test.py -n $(N) --config $(CONFIG) --part $(PART)

# Second-pass test: run N designs through Vivado on a remote host (default CCL1)
# up to block-design validation, no synthesis. Override with N=, HOST=, JOBS=.
# Add SYNTH=1 to run full synthesis and pass only if synth.dcp is produced;
# synthesis is much slower, so also bump the per-design TIMEOUT (seconds).
HOST ?= CCL1
JOBS ?= 75
SYNTH ?=
TIMEOUT ?= 900
vivado-test: .venv/bin/activate
	$(IN_ENV) python vivado_test.py -n $(N) --config $(CONFIG) --part $(PART) --host $(HOST) --jobs $(JOBS) --timeout $(TIMEOUT) $(if $(SYNTH),--synth,)

env: .venv/bin/activate
cleanenv:
	rm -rf .venv

.venv/bin/activate: requirements.txt
	python3 -m venv .venv
	$(IN_ENV) pip install -r requirements.txt

.PHONY: env run run-bd all vivado vivado-bd cleanenv smoke vivado-test
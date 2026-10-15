LATEXMK ?= latexmk
LATEX_BUILD := .latex-build

.PHONY: writeup clean-writeup
writeup:
	mkdir -p "$(LATEX_BUILD)"
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -outdir="$(LATEX_BUILD)" part3b-writeup.tex
	cp "$(LATEX_BUILD)/part3b-writeup.pdf" part3b-writeup.pdf

clean-writeup:
	rm -rf "$(LATEX_BUILD)"

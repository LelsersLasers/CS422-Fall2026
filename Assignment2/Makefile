LATEXMK ?= latexmk
LATEX_BUILD := .latex-build

.PHONY: writeup writeup-3a clean-writeup
writeup:
	mkdir -p "$(LATEX_BUILD)"
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -outdir="$(LATEX_BUILD)" part3b-writeup.tex
	cp "$(LATEX_BUILD)/part3b-writeup.pdf" part3b-writeup.pdf

writeup-3a:
	mkdir -p "$(LATEX_BUILD)"
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -outdir="$(LATEX_BUILD)" part3a-writeup.tex
	cp "$(LATEX_BUILD)/part3a-writeup.pdf" part3a-writeup.pdf

clean-writeup:
	rm -rf "$(LATEX_BUILD)"

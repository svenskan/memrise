all: input.csv
	python -m memrise.main --input $< --output output

.PHONY: all

# opentelemetry-exporter-python
The honeycomb.io Python exporter for OpenTelemetry

### Install

```bash
pip install opentelemetry-ext-honeycomb
```

### Initialize

```python
# note writekey and dataset may be specified in the environment instead
exporter = HoneycombSpanExporter(
	service_name="test-service",
	writekey=<HONEYCOMB_WRITEKEY>,
	dataset=<HONEYCOMB_DATASET>,
)
span_processor = BatchExportSpanProcessor(exporter)
tracer.add_span_processor(span_processor)
```

### Development

This package uses [poetry](https://python-poetry.org/) for packaging and dependency management. To install a development copy into a virtualenv locally, run:

```
$ poetry install
```

And then activate the appropriate virtualenv.

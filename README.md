# pretix Furbadge Plugin

**WARNING: This is a purely testing repository for internal usage !!!**

A Pretix plugin that adds BLIK as Payment Method for built-in Stripe plugin.

## Development

This project uses Python and pretix plugin conventions.

Recommended checks before opening a pull request:

```bash
python -m pip install -U pip
pip install -e .[dev]
python -m compileall pretix_stripe_blik_payment
python -m mypy pretix_stripe_blik_payment --config-file pyproject.toml
python -m pyright
```

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

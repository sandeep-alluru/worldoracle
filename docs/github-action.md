# GitHub Action

Use worldoracle directly in your GitHub Actions workflow:

```yaml
- name: worldoracle
  uses: sandeep-alluru/worldoracle@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install worldoracle
  run: pip install worldoracle

- name: Run worldoracle
  run: worldoracle --help
```

# Python Environment

This project uses a local virtual environment at `.venv` with Python 3.11.

## Activate

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation scripts, run commands through the interpreter
directly:

```powershell
.\.venv\Scripts\python.exe -m pip list
.\.venv\Scripts\python.exe -m jupyter lab
```

## Installed Kernel

The notebook kernel has been registered as:

```text
Python 3.11 (MLmodel)
```

## Reinstall Dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
```

Run commands from the repository root so relative paths such as `data/` and
`course_recommender_artifacts_final/` resolve correctly.

For backend-only runtime:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-production.txt
```

## Notes

- TensorFlow is installed as the native Windows CPU runtime.
- `tf.config.list_physical_devices("GPU")` returned an empty list in this setup.
- Use WSL2/CUDA later if GPU training is required.

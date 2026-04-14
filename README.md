# Kaggle Plugin for Dify

**Author:** [ki3dn](https://github.com/ki3nd)   
**Type:** tool   
**Github Repo:** [https://github.com/ki3nd/kaggle-dify-plugin](https://github.com/ki3nd/kaggle-dify-plugin)   
**Github Issues:** [issues](https://github.com/ki3nd/kaggle-dify-plugin/issues)   

Run and manage [Kaggle](https://www.kaggle.com) kernels directly from your Dify workflows. Write Python code, choose your accelerator, poll for completion, and retrieve output files — all without leaving your AI pipeline.

## Setup

1. Go to **kaggle.com → Settings → API → Create New API Token**.
2. Copy the token value (a long alphanumeric string).
3. In Dify, open the plugin settings and paste the token into the **KAGGLE_API_TOKEN** credential field.

## Tools

### List User Kernels

List kernels owned by any Kaggle user, or by the authenticated account when no username is supplied.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `username` | No | Kaggle username. Leave empty to list your own kernels. |

**Returns:** a list of `{ kernel_id, kernel_name }` entries.

---

### Create Kernel

Create a new Kaggle kernel with a minimal Python starter script. The kernel slug is derived automatically from the title.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `title` | Yes | — | Kernel title (minimum 5 characters). Must be unique among your kernels. |
| `is_private` | No | `true` | Whether the kernel is private. |
| `enable_internet` | No | `true` | Whether the kernel has internet access during execution. |

**Returns:** kernel metadata including `id`, `url`, and settings.

---

### Run Kernel Code

Push Python code to an existing kernel and trigger a new run. The kernel is converted to a Python script type before pushing, so the provided code replaces the current script entirely.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `kernel_id` | Yes | — | `owner/kernel-slug` or just `kernel-slug` (auto-prefixed with your username). |
| `code` | Yes | — | Python source code to run. |
| `accelerator` | No | `None` | `None`, `NvidiaTeslaP100`, `NvidiaTeslaT4`, or `TpuV5E8`. |

**Returns:** push result including `url`, `version_number`, and any errors.

---

### Get Kernel Status

Fetch the latest run status and full metadata for a kernel.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `kernel_id` | Yes | `owner/kernel-slug` or just `kernel-slug` (auto-prefixed with your username). |

**Returns:** `{ status, kernel_id, status_details, metadata }`.

Possible status values: `queued`, `running`, `complete`, `error`, `cancelled`.

---

### Get Kernel Metadata

Fetch the configuration metadata for a kernel (language, kernel type, datasets, accelerator, etc.) without checking its run status.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `kernel_id` | Yes | `owner/kernel-slug` or just `kernel-slug` (auto-prefixed with your username). |

**Returns:** full kernel metadata object.

> If the kernel does not exist or is private/inaccessible, a descriptive message is returned instead of raising an error.

---

### Get Kernel Output

Download a specific output file from a completed kernel, or retrieve only the execution logs when no file path is given.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `kernel_id` | Yes | `owner/kernel-slug` or just `kernel-slug` (auto-prefixed with your username). |
| `file_path` | No | Path to the output file. Accepts absolute Kaggle paths (`/kaggle/working/output.csv`) or relative paths (`images/result.png`). Leave empty to return logs only. |

**Returns:**
- **With `file_path`:** file content (text, JSON, image, or binary blob) followed by `{ kernel_id, file_path, logs }`.
- **Without `file_path`:** `{ kernel_id, logs }` — no file is downloaded.

If the kernel is still running or queued, an informative message is returned and the download is skipped. If the kernel failed, the failure message and status are returned.

---

## Kernel ID shorthand

Every tool that accepts a `kernel_id` supports a short form. If you omit the `owner/` prefix, the plugin automatically prepends the authenticated user's username:

```
my-analysis          →  your-username/my-analysis
alice/her-analysis   →  alice/her-analysis  (unchanged)
```

## Typical workflow

```
Create Kernel  →  Run Kernel Code  →  Get Kernel Status (poll)  →  Get Kernel Output
```

1. **Create Kernel** once to get a persistent `kernel_id`.
2. **Run Kernel Code** to push new code and trigger execution.
3. **Get Kernel Status** in a loop until `status == "complete"`.
4. **Get Kernel Output** to retrieve result files or logs.

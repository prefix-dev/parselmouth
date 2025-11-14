# Local Pipeline Testing with MinIO

This guide explains how to test the complete parselmouth pipeline locally using MinIO (an S3-compatible object storage) instead of Cloudflare R2.

## Prerequisites

- Docker and Docker Compose installed
- Python environment with parselmouth installed (`pixi install`)

## Quick Start

### Interactive Mode (Recommended - One Command!)

The easiest way to get started - this automatically starts MinIO and runs the interactive pipeline:

```bash
# This single command does everything:
# 1. Starts MinIO (docker-compose up -d)
# 2. Shows current storage statistics
# 3. Guides you through configuration
# 4. Runs the pipeline
pixi run test-interactive
```

### Manual Mode (More Control)

If you want more control or prefer command-line arguments:

#### 1. Start MinIO

```bash
# Start MinIO container
pixi run start-minio

# Wait a few seconds for MinIO to initialize
# MinIO UI will be available at http://localhost:9001
```

#### 2. Run the Pipeline

**With interactive prompts:**
```bash
# Run with flag (MinIO must already be running)
pixi run test-pipeline --interactive
# or shorthand:
pixi run test-pipeline -i
```

**With command-line arguments:**

```bash
# Run with defaults (pytorch, noarch, package names starting with 't', fresh mode)
pixi run test-pipeline

# Or run with custom options
pixi run test-pipeline --help
```

**Command-line options:**
- `--channel`: Choose channel (conda-forge, pytorch, bioconda)
- `--subdir`: Choose subdir (noarch, linux-64, osx-arm64, etc.)
- `--letter`: Filter package NAMES by first character, or use 'all' for everything
- `--mode`: Processing mode - 'fresh' (default, reprocess all) or 'incremental' (skip existing)
- `--interactive` or `-i`: Enable interactive prompts with statistics

**Examples:**
```bash
# Interactive mode (shows stats, guides you through options)
pixi run test-interactive

# Test pytorch with packages named torch*, torchvision*, etc.
pixi run test-pipeline

# Test conda-forge with packages named numpy*, napari*, etc.
pixi run test-pipeline --channel conda-forge --letter n

# Test incrementally (skip packages already processed)
pixi run test-pipeline --mode incremental

# Test ALL packages in bioconda noarch (slow!)
pixi run test-pipeline --channel bioconda --letter all
```

### 3. Explore the Data

**MinIO Web UI:**
- URL: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

Browse the `conda` bucket to see:
- `hash-v0/` - Hash-based mappings
- `relations-v1/` - Relations table
- `pypi-to-conda-v1/` - PyPI lookup files

### 4. Clean Up

```bash
# Clean everything (stops MinIO and removes all data)
pixi run clean-all

# Or clean separately:

# Clean all local data (cache + outputs, keep MinIO running)
pixi run clean-local-data

# Just remove output files
pixi run clean-outputs

# Just remove conda package cache (can grow to 1GB+)
pixi run clean-cache
```

**What gets cleaned:**

| Command | What it removes |
|---------|----------------|
| `clean-outputs` | Output directories |
| `clean-cache` | Downloaded conda packages (can be GB) |
| `clean-local-data` | Cache + outputs (keeps MinIO) |
| `clean-all` | Everything + stop MinIO |

**Details:**
- `local_test_output/` - Local pipeline test outputs
- `output/` - Updater outputs
- `output_index/` - Index files
- `output_relations/` - Relations table files
- `test_production/` - Production test files
- `conda_oci_mirror/cache/` - Cached conda packages (grows with each run)
- MinIO container and volumes (with `clean-all`)

**💡 Tip:** Run `pixi run clean-cache` periodically to reclaim disk space. The cache grows based on how many packages you process and will be rebuilt as needed.

## What the Pipeline Does

The test script runs through the complete workflow:

1. **Producer** - Identifies new packages to process
2. **Updater** - Downloads and processes conda packages
3. **Merger** - Combines partial indices into master index
4. **Relations** - Generates v1 relations table and PyPI lookups
5. **Verification** - Checks that all data is accessible

## Configuration

### MinIO Settings

The default configuration in `docker-compose.yml`:
- S3 API Port: 9000
- Web UI Port: 9001
- Default bucket: `conda`
- Credentials: `minioadmin` / `minioadmin`

### Testing Different Channels

Use command-line arguments to test different channels:

```bash
# PyTorch (default - small, fast)
pixi run test-pipeline

# Conda-forge (large - takes longer)
pixi run test-pipeline --channel conda-forge

# Bioconda (medium size)
pixi run test-pipeline --channel bioconda
```

### Testing Specific Subdirs and Packages

Use `--subdir` and `--letter` to narrow down what you process:

```bash
# Process only package names starting with 'n' (numpy, napari, etc.)
pixi run test-pipeline --letter n

# Process package names starting with 'p' in linux-64 (pandas, pytorch, etc.)
pixi run test-pipeline --subdir linux-64 --letter p

# Process ALL packages (warning: very slow!)
pixi run test-pipeline --letter all
```

### Testing Multiple Channels

Multiple channels can coexist in the same bucket, separated by path prefixes. This mirrors production behavior:

```bash
# Process pytorch first (fresh mode - reprocess everything)
pixi run test-pipeline --channel pytorch --letter t

# Process conda-forge second (both will be in the same bucket)
pixi run test-pipeline --channel conda-forge --letter n

# Process bioconda third
pixi run test-pipeline --channel bioconda --letter a

# Run incrementally to only process new packages
pixi run test-pipeline --channel pytorch --mode incremental
```

In MinIO you'll see:
```
conda/
├── hash-v0/
│   ├── {sha256}  (shared across all channels - same hash = same package)
│   ├── {sha256}
│   ├── ...
│   ├── pytorch/
│   │   └── index.json  (references hashes for pytorch packages)
│   ├── conda-forge/
│   │   └── index.json  (references hashes for conda-forge packages)
│   └── bioconda/
│       └── index.json  (references hashes for bioconda packages)
├── relations-v1/
│   ├── pytorch/
│   │   ├── relations.jsonl.gz
│   │   └── metadata.json
│   ├── conda-forge/
│   │   ├── relations.jsonl.gz
│   │   └── metadata.json
│   └── bioconda/
│       ├── relations.jsonl.gz
│       └── metadata.json
└── pypi-to-conda-v1/
    ├── pytorch/
    │   ├── torch.json
    │   └── ...
    ├── conda-forge/
    │   ├── numpy.json
    │   └── ...
    └── bioconda/
        └── ...
```

**Note:** Individual package mappings (`hash-v0/{sha256}`) are shared across all channels because the same package with the same SHA256 can exist in multiple channels. Only the **index files** and **relations data** are separated by channel.

## Advanced Usage

### Using MinIO with Existing Scripts

You can use MinIO with any parselmouth command by setting the endpoint:

```bash
export R2_PREFIX_ENDPOINT="http://localhost:9000"
export R2_PREFIX_ACCESS_KEY_ID="minioadmin"
export R2_PREFIX_SECRET_ACCESS_KEY="minioadmin"
export R2_PREFIX_BUCKET="conda"

# Now run any command
pixi run parselmouth update-v1-mappings --upload --channel pytorch
```

Note: The system also supports the standard `AWS_ENDPOINT_URL` environment variable for compatibility with boto3 tools.

### Accessing Data via CLI

```bash
# List all buckets
aws --endpoint-url http://localhost:9000 \
    s3 ls

# List files in a bucket
aws --endpoint-url http://localhost:9000 \
    s3 ls s3://conda/hash-v0/

# Download a specific file
aws --endpoint-url http://localhost:9000 \
    s3 cp s3://conda/relations-v1/pytorch/relations.jsonl.gz ./
```

### Persisting Data Between Runs

MinIO data is stored in a Docker volume by default. The `pixi run clean-all` command will stop MinIO and remove all volumes.

If you want to manually manage docker-compose:

```bash
# Stop without removing volumes
docker-compose down

# Restart with existing data
docker-compose up -d

# Remove everything including volumes
docker-compose down -v
```

## Troubleshooting

### MinIO Not Starting

```bash
# Check container logs
docker-compose logs minio

# Ensure ports are available
lsof -i :9000
lsof -i :9001
```

### Connection Refused

Make sure MinIO is running and healthy:

```bash
# Check container status
docker-compose ps

# Wait for health check
docker-compose logs minio-init
```

### Empty Index

If the pipeline completes but data is missing:

1. Check that packages exist upstream in the conda channel
2. Try a different subdir (e.g., `linux-64` instead of `noarch`)
3. Check MinIO logs for errors

### SSL/TLS Errors

MinIO runs on HTTP by default. Make sure you're using `http://` not `https://`:

```bash
export R2_PREFIX_ENDPOINT="http://localhost:9000"  # Correct
```

## Comparing with Production

### Differences from R2

| Feature | MinIO (Local) | Cloudflare R2 (Production) |
|---------|---------------|----------------------------|
| Endpoint | `http://localhost:9000` | `https://*.r2.cloudflarestorage.com` |
| Credentials | `minioadmin` | Cloudflare API tokens |
| SSL | HTTP only | HTTPS only |
| Performance | Local disk | Global CDN |
| Cost | Free | Pay per operation |

### Testing Changes Safely

The local setup is perfect for:
- Testing pipeline changes without affecting production
- Developing new features
- Debugging issues
- Validating data transformations
- Performance testing

## Example Workflow

```bash
# 1. Start fresh (clean everything first)
pixi run clean-all

# 2. Start MinIO
pixi run start-minio

# 3. Run pipeline (fresh mode)
pixi run test-pipeline

# 4. Verify in UI
open http://localhost:9001

# 5. Test incremental update (skips existing packages)
pixi run test-pipeline --mode incremental

# 6. Check that existing packages were skipped (look for logs)

# 7. Clean up
pixi run clean-all
```

## Integration Tests

The integration tests (`tests/test_integration_s3_pipeline.py`) use moto to mock S3. For full end-to-end testing with real S3 behavior, use this MinIO setup instead.

To run tests against MinIO:

```bash
# Start MinIO
pixi run start-minio

# Set environment
export R2_PREFIX_ENDPOINT="http://localhost:9000"
export R2_PREFIX_ACCESS_KEY_ID="minioadmin"
export R2_PREFIX_SECRET_ACCESS_KEY="minioadmin"
export R2_PREFIX_BUCKET="conda"

# Run specific test
pixi run test
```

## References

- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

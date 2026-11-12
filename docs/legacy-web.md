# Legacy Web Version

The Web-related code mainly includes:

- `sau_backend.py`
- `sau_backend/`
- `sau_frontend/`

It belongs to an earlier stage of the project and is no longer maintained as the main line.

## Current status

- Kept as a legacy version
- Kept as a reference for the earlier API / Web wrapper approach
- Not promised to run directly now
- Not promised to be fully in sync with the latest `uploader/` and `sau_cli.py`

## Why this is explained separately

The project is currently being restructured as a whole, and the main line has moved to:

- `uploader/`: core platform implementations
- `sau_cli.py`: main CLI entry
- `skills/`: skills for agents

So the README no longer introduces the Web version as the main entry, to avoid giving new users the impression that it is the most stable way to use the project.

## If you still want to study the legacy Web version

You can refer to these files:

- `sau_backend/README.md`
- `sau_frontend/README.md`
- `sau_backend.py`

But expect that:

- The API contract may not match the current main line
- Platform coverage may lag behind the current `uploader/`
- Dependencies and the way to run it may need your own troubleshooting

## Recommended entry points now

To use the current main-line capabilities, look first at:

- `uploader/`
- `sau_cli.py`
- `docs/CLI.md`
- `skills/douyin-upload/SKILL.md`

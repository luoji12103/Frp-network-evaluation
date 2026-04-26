# mc-netprobe Windows Client

This package targets Windows 10/11 x64.

## First Run

1. Unzip `mc-netprobe-client-windows-x64-<version>-<build-ref>.zip`.
2. Run `mc-netprobe-tray.exe`.
3. Choose `Initialize / Reconfigure`.
4. Approve the UAC prompt.
5. Enter Panel URL, Pair Code, Node Name, and Listen Port.

The initialized runtime is copied to:

```text
C:\ProgramData\mc-netprobe\client
```

## Tray Shortcuts

- `Open Config File` opens `C:\ProgramData\mc-netprobe\client\config\agent\client.yaml`.
- `Open Logs Folder` opens `C:\ProgramData\mc-netprobe\client\logs`.
- `Open Panel` opens the configured panel URL.

The background service starts before user login. The tray starts after user login and acts as a control surface.

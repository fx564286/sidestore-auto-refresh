# V49 – verified JIT return and PID handoff (limited scope)

V48 sample logs are from SideStore inside LiveProcess, not necessarily
Madeira itself. PID changes are normal after restarting a process.

V49 changes the LiveContainer launcher; it does not touch credentials,
provisioning, app IDs, extensions, or guest storage.

* Classic/non-multitask launch: poll the actual host CS_DEBUGGED flag
  while its JIT waiting sheet is open (maximum 90 seconds). If and only
  if debugged, close the sheet and launch the selected guest without
  a second manual click. No unconditional timed success.
* LiveProcess/multitask launch: build the StikDebug PID-target URL
  with URLComponents to avoid query injection from script-data.
  Reject invalid PID/host ID and show a failure if the helper URL
  was not accepted by iOS. Log the PID and provider.
* Host CS_DEBUGGED or a successful URL open does not prove that the
  guest's JIT pool is executable. Madeira must still complete its
  own script and live-debugger handshake.

LIMITATION: external StikDebug owns its own "Returning to..." UI;
V49 cannot force it to return or keep its debugger connection alive.
The LiveProcess guest cannot be validated using the host's CS_DEBUGGED.

On-device acceptance: verify classic launch auto-return when the host
becomes debuggable, failure remains pending when it does not, PID
handoff targets the new LiveProcess PID, Madeira confirms actual
executable JIT pool creation, and earlier guest keyboard/audio
resume and signing/data-preservation regressions remain intact.

No device validation or install is claimed by source-level checks.

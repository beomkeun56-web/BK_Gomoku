# Cornix LP ZMK config

ZMK firmware for the PandaKB Cornix LP (48 keys + 2 knobs), laid out to match the Sofle RGB config.
Board definitions come from [hitsmaxft/zmk-keyboard-cornix](https://github.com/hitsmaxft/zmk-keyboard-cornix).

## Layout

- **Base**: QWERTY, home-row mods (GUI/Alt/Shift/Ctrl), Hyper on `'`, Esc tap / `` ` `` hold, Tab tap / Globe (Fn) hold.
- **Lower** (left thumb): symbols, right-hand numpad, Hyper shortcuts on A O D S.
- **Raise** (right thumb): navigation and editing keys.
- **Adjust** (middle thumbs): numbers on the Q-P row, F-keys on the bottom row, modifiers as on Base.
- **System** (Lower + Raise): Bluetooth profiles, USB/BLE output, bootloader.
- Left knob: volume, press mutes. Right knob: page up/down, press is middle click.

Keymap: `config/cornix.keymap`. Settings: `config/cornix.conf`. Build targets: `build.yaml`.

## Build

Push to GitHub. Actions builds `cornix_left`, `cornix_right` and `cornix_reset` UF2 files.

## Flash

1. Unpair the keyboard from every host first.
2. Double-tap the reset button on a half; it mounts as a USB drive.
3. First time, and whenever pairing misbehaves: drag `cornix_reset.uf2` onto **both** halves.
4. Drag `cornix_left.uf2` onto the left half and `cornix_right.uf2` onto the right half.
5. Reset both halves together, then pair from the host.

## Going back to stock RMK / Vial

Stock PandaKB firmware V1.12 is kept in `~/Development/cornix-stock-firmware/` and published at
<https://github.com/PandaKBLab/Cornix-Split-Low-Profile-Wireless-Keyboard>. Older versions are in `rmkfw/`.
Double-tap reset and drag `cornix-left.uf2` / `cornix-right.uf2` onto the matching half.
The bootloader is never changed, so this always works. `bootloader/` holds recovery files for a half
that no longer enters UF2 mode.

## LEDs

The `cornix_indicator` shield is enabled. LED 1 shows battery (green / yellow / red, breathing green
while charging). LED 2 shows connection (colour per Bluetooth profile, pulsing while pairing, red when
disconnected, magenta when the halves lose each other). Power to the LEDs is cut one second after they
go idle. Remove the shield lines from `build.yaml` to turn them off.


## 범근님 브랜치 메모(260929)
이 브랜치는 BK_Gomoku 저장소 안의 독립 브랜치(orphan)로 게임 코드와 무관하다. Cornix LP ZMK 설정 전용. 빌드 결과는 firmware/ 폴더에 자동 커밋된다.

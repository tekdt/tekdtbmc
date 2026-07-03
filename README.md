# TekDT BMC

**TekDT BMC** is a tool for creating bootable devices that can hold multiple operating system installers, compatible with various computer configurations, and automates the OS installation process.

- **Software name:** TekDT BMC  
- **Author:** TekDT  
- **Description:** USB boot creation software compatible with diverse hardware, integrating automated software installation after Windows setup.  
- **Release date:** December 29, 2025  
- **Version:** 1.0.6  
- **Email:** dinhtrungtek@gmail.com  
- **Facebook:** @tekdtxyz

---

## Download

- Latest version: [https://github.com/tekdt/tekdtbmc/releases/latest/download/TekDT_BMC.zip](https://github.com/tekdt/tekdtbmc/releases/latest/download/TekDT_BMC.zip)  
- SHA256 hash of TekDT’s signature: `4ef06065990138ab401948b95f536272` – only if the hash matches is it authentic from TekDT.

---

## Usage Instructions

The program interface has a total of 3 steps: **SELECT USB**, **SELECT OR DOWNLOAD ISO**, **ADD SOFTWARE FOR AUTOMATIC INSTALLATION AFTER WINDOWS SETUP**.

### Step 1: Select USB device
- **Dropdown list:** Shows all available devices.
- **Show hard disks:** This feature is currently unstable (not recommended; may cause data loss).

### Step 2: Select ISO
- **Add ISO from computer:** Choose an ISO already on your hard drive. Using official ISOs from Microsoft is recommended over custom ones.
- **Remove selected ISO:** Select an ISO and click this button to remove it from the list.
- **Auto‑download from Microsoft:** If you don’t have an ISO yet, tick this option and batch‑download the ISOs you want.
- **Download checked items:** After selecting the ISO versions you want to download, click this button to download all ticked ISOs one by one.

### Step 3: Select software to install automatically after Windows installation finishes
- From the software list, click **Download** (if the software is not yet available – requires internet) or **Add** to include it in the automatic installation queue. The program will automatically copy **TekDT AIS** to the boot device and configure it to run automatically – you don’t need to do anything else.
- After everything is set, click **Start** to create the USB drive.

There are additional options under the **Menu** button (top‑left corner):

- **Partition scheme:** Default is **GPT** for better compatibility (as per Ventoy documentation); if not compatible, choose **MBR**.
- **Format:** Default is **ExFAT**; you can select other formats.
- **Fill capacity:** Default is **Yes**. If set to **Yes**, your USB drive will be filled with dummy data to leave 0 bytes free. This reduces damage from viruses (especially shortcut viruses) and prevents infection of other computers.
- **Strip unused editions from ISO:** Default is **Yes**. If **Yes**, when you select a specific Windows edition (e.g., Pro) in Step 2, all other editions (Home, Education, etc.) are completely removed, keeping only the selected edition. This takes a little extra time but frees up space on your device.
- **Filter and keep only added software:** Default is **Yes**. In Step 3, only software you have **Added** will be included for automatic installation. The program will remove software not added (i.e., not needed for unattended installation) to save storage space.
- **Theme:** Default is **None** (not selected). This option applies to the boot screen (Ventoy support). If you have a custom theme, copy it into the `Themes` folder of TekDT BMC.
- **Download drivers:** Adds the option to download drivers and integrate them into the Windows PE boot process and install them after Windows setup. By default, if the `db.sqlite` file or the driver pack `DP_MassStorage_*.7z` is missing in Step 3, the program will block and automatically download these two files before proceeding. It is also recommended to download `DP_Touchpad_*.7z` and `DP_WLAN-WiFi_*.7z`.
- **Software info:** Displays information about this software and its author – me.

---

## Note

This program requires an internet connection for its first run, because it needs to download necessary tools into the `Tools` folder – such as Ventoy, 7z, aria2, wimlib, TekDT AIS, etc. The third interface embeds the TekDT AIS interface, so downloading new software also requires internet; however, if you have already downloaded some (or all) of the software you need, you can use it offline afterwards.

---

## Disclaimer

- TekDT is not responsible for any use of this software/script, or for any modified/repackaged versions obtained from other sources. You are free to use this software/script at no cost – trust it. TekDT will not collect your information or harm your computer.
- If you do not trust this software/script, please delete the downloaded files.

---

## Support

We welcome and appreciate any feedback to help improve this software/script. You can reach TekDT via:

- **Zalo:** 0944.095.092  
- **Email:** dinhtrungtek@gmail.com  
- **Facebook:** @tekdtxyz  

---

## Contributions

To help make the software/script more complete and feature‑rich, TekDT needs motivation to maintain it. If this software/script is useful for your work, please consider a small contribution. Your sincere support is greatly appreciated.

- **MOMO:** [https://me.momo.vn/TekDT1152](https://me.momo.vn/TekDT1152)  
- **Biance ID:** `877691831`
- **USDT (BEP20):** `0x53a4f3c22de1caf465ee7b5b6ef26aed9749c721`

---

**Vietnamese version** is available at: [README_VI.md](https://github.com/tekdt/tekdtbmc/blob/main/README_VI.md) (original Vietnamese).
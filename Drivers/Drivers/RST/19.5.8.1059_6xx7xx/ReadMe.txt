**************************************************************************
**************************************************************************
*                           Installation Readme for 
*    Intel(R) Rapid Storage Technology (Intel(R) RST) with Support for:
*     - Intel(R) Optane(TM) Memory System Acceleration^^
*     - RAID 0/1/5/10^^
*     - CPU Attached Storage^^
*      ^^ NOTE: Support for this feature is determined by your hardware configuration
*
* This document makes references to products developed by Intel. There are some 
* restrictions on how these products may be used, and what information may be disclosed to 
* others. Please read the Disclaimer section at the end of this document, and contact 
* your Intel field representative if you would like more information.
*
**************************************************************************
**************************************************************************

**************************************************************************
* Intel is making no claims of usability, efficacy or warranty. The INTEL SOFTWARE LICENSE 
* AGREEMENT contained herein completely defines the license and use of this software.
**************************************************************************

**************************************************************************
*                 CONTENTS OF THIS DOCUMENT                              *
**************************************************************************

This document contains the following sections:

1.  Supported Platforms/Chipsets
2.  System Requirements
3.  Language Support
4.  INTEL(R) OPTANE(TM) TECHNOLOGY BASED SYSTEM ACCELERATION 
5.  Installing the Software
7.  Verifying Installation of the Software
8.  Advanced Installation Instructions
9.  Identifying the Software Version Number
10. Uninstalling the Software
11. Entering the pre-OS User Interface
12. Pre-OS RAID Volume Management
13. Options to RESET the RAID volume in the Pre-OS UI's
14. Verifying the Version of the Pre-OS UEFI Driver/OptionROM SOFTWARE

**************************************************************************
* 1.  SUPPORTED PLATFORMS/CHIPSETS
**************************************************************************
This Intel(R) Rapid Storage Technology Release is designed to provide functionality
for the following Storage Controllers :

1.a VMD Platforms -  
- Intel(R) 13th Generation platform
   Desktop
   - Z790
- Intel(R) 12th Generation platform
   Desktop
   Intel(R) 600 Series Chipset Family:
   - B660
   - H610
   - H670
   - Z690
- Intel(R) 11th Generation platform
   Mobile Low Power (LP)
   - Premium UP3
   - Premium UP4
   Mobile Halo
   Intel(R) 500 Series Chipset Family:
   - HM570
   - QM580
   - WM590


**************************************************************************
* 2.  SYSTEM REQUIREMENTS
**************************************************************************

A.  The system must contain one of the Intel controllers listed in Section 1 “SUPPORTED 
    PLATFORMS/CHIPSETS” above and one of the following types of processors***:
    - Intel(R) vPro(TM)
    - Intel(R) Celeron(R)
    - Intel(R) Pentium(R)
    - Intel(R) Core™ i3, i5, i7 or i9
    - Intel(R) Xeon(R) processor family

***Note: There are certain Intel(R) Rapid Storage Technology features that are only 
   enabled based upon the system's processor
    
B.  The system must be running one of the following operating systems (no other Windows
    OS versions are supported):
    - Microsoft Windows* 10 x64 Edition** (current RTM version)
    

C.  The following operating systems are not supported in any versions or updates:
    - Linux*
    - UNIX*
    - BeOS*
    - MacOS*
    - OS/2*

D.  The system should contain at least the minimum system memory required by the operating
    system. Consult your computer system and OS vendor.
    *Other names and brands may be claimed as the property of others.

**************************************************************************
* 3.  LANGUAGE SUPPORT
**************************************************************************

Below is a list of the languages (and their abbreviations) for which the Intel(R) Rapid 
Storage Technology software has been localized. The language code is listed in parentheses 
after each language.

ARA: Arabic (Saudi Arabia)       (0401)
CHS: Chinese (Simplified)        (0804)
CHT: Chinese (Traditional)       (0404)
CSY: Czech                       (0405)
DAN: Danish                      (0406)
NLD: Dutch                       (0413)
ENU: English (United States)     (0409)
FIN: Finnish                     (040B)
FRA: French (International)      (040C)
DEU: German                      (0407)
ELL: Greek                       (0408)
HEB: Hebrew                      (040D)
HUN: Hungarian                   (040E)
ITA: Italian                     (0410)
JPN: Japanese                    (0411)
KOR: Korean                      (0412)
NOR: Norwegian                   (0414)
PLK: Polish                      (0415)
PTB: Portuguese (Brazil)         (0416)
PTG: Portuguese (Standard)       (0816)
RUS: Russian                     (0419)
ESP: Spanish                     (0C0A)
SVE: Swedish                     (041D)
THA: Thai                        (041E)
TRK: Turkish                     (041F)

**************************************************************************
* 4  INTEL(R) OPTANE(TM) TECHNOLOGY BASED SYSTEM ACCELERATION
**************************************************************************

4.A  INTEL(R) OPTANE(TM) MEMORY SUPPORTED PLATFORMS/CHIPSETS
--------------------------------------------
Intel(R) Optane(TM) Technology based System Acceleration is designed to provide 
functionality for the following Storage Controllers of the Intel PCH:

4.A.1 VMD Platforms -  
Intel(R) 11th Generation Core Processor Family Platform VMD Controller
 Mobile Low Power (LP)
 - Premium UP3
 - Premium UP4
 Mobile Halo
Intel(R) 500 Series Chipset Family:
 - HM570
 - QM580
 - WM590

  
   
4.B  SYSTEM REQUIREMENTS for INTEL(R) OPTANE(TM) MEMORY SYSTEM ACCELERATION 
--------------------------------------------------------------
4.B.1 VMD platforms - 

i.  The system must contain one of the Intel controllers listed in Section 1 “SUPPORTED 
    PLATFORMS/CHIPSETS” above and one of the following types of processors***:
    - Intel(R) vPro
    - Intel(R) Core(TM) i3, i5, i7 or i9 processors
    - Intel(R) Xeon(R) E3 v6 processor family    
ii.  The system must be running one of the following operating systems (no other Windows
     OS versions are supported):
        - Microsoft Windows* 10 x64 Edition (current RTM)
iii.  The system should contain at least the minimum system memory required by the
      operating system. Consult your computer system and OS vendor.
        *Other names and brands may be claimed as the property of others
iv.   The system must contain one of the following supported Intel(R) Optane(TM)
      technologies populated into the storage connector labeled “Intel(R) Optane(TM)
      Memory Ready” or “Intel(R) Optane(TM) Ready”:
	   -Intel(R) Optane(TM) memory modules
v.    The system must contain one of the following supported backend (slow media system
      disk) storage devices: 
         -SATA HDD
         -SATA SSD
		 -QLC NVMe drives 
         -SATA SSHD**
          **Self-pinning SSHDs only, SSHDs that use the Hybrid Information Feature Set are
            not supported
vi.   VMD device should ALWAYS be ENABLED in the BIOS. 
vii.  System integrators can choose the storage devices on the platform to be
	  under VMD controlled in order to create the desired storage configuration.
	  VMD-controlled storage devices will be accessed through the Intel(R) RST VMD driver.
	  Intel® RST driver for VMD only supports SATA Controller when SATA Controller is
	  mapped under VMD.
viii. For the storage devices that system integrators do not configure to be under
	  VMD control, Windows* Inbox driver will be used to access the device.

	  


4.C  CONFIGURING INTEL(R) OPTANE(TM) TECHNOLOGY BASED SYSTEM ACCELERATION
-------------------------------------------------------------------------

I: INTEL(R) RST UI/Installer

This method is targeted for experienced users who want to have control of the
configuration process are recommended to use this method.

1. Obtain the Intel(R) RST SW/driver installation package and run the executable (SetupRST.exe)
2. Install the defaults and reboot the computer
3. From Windows desktop, find and launch the Intel® Optane(TM) Memory and Storage Management application.
4. The application will open to the ‘Manage’ page
5. Click the ‘Intel(R) Optane(TM) Memory’ tab
6. Select disk configuration
7. Click the “Enable Intel(R) Optane(TM) Memory".
8. Choose mode for Intel(R) Optane(TM) Memory and click Next
9. Check "Erase all data on Intel(R) Optane(TM) memory module"
10. Click the “Enable” link to start the enabling process
11. Depending on the size of your Intel(R) Optane(TM) memory module, a progress bar may be displayed
12. Let progress bar complete to 100%
13. Finalize operation
14. Click the [Reboot] button to complete the process
15. System reboots into Windows to complete the enabling process.
    
* 4.D  DISABLING INTEL(R) OPTANE(TM) TECHNOLOGY BASED SYSTEM ACCELERATION
-------------------------------------------------------------------------
Pre-OS
1. Restart the computer and enter the BIOS
2. Enter the Intel(R) RST HII UI
3. Select the Intel(R) Optane(TM) Memory volume, then select ‘Deconcatenate’ and complete the following:
     a. [X] Checkbox to preserve user data upon deconcatenation; Checked is the default
     b. <No> Decision box to confirm deconcatenation action; Yes or No (No is default)

Intel(R) Optane(TM) Memory and Storage Management UI 
1. From Windows desktop, find and launch the Intel® Optane(TM) Memory and Storage Management application.
2. The application will open to the ‘Manage’ page
3. Click the ‘Intel(R) Optane(TM) Memory’ tab
4. Click the “Disable” link to start the disabling process
5. Confirm disabling Intel® Optane Memory.
6. Click Disable and wait for the progress to complete 
7. Click the [Reboot] button to complete the process



**************************************************************************
* 5.  INSTALLING THE SOFTWARE
**************************************************************************

6.1 General Installation Notes

a.  If you are installing the operating system on a computer configured for RAID or AHCI
    mode, you may pre-install the Intel(R) Rapid Storage Technology driver using the 
    "F6" (Load Driver) installation method described in section 6.3 below.

b.  If you’re installing the operating system on a computer configured for ‘Intel(R) Smart 
    Response Technology’ or ‘System Acceleration with Intel(R) Optane(TM) Technology’, you 
    must pre-install the Intel(R) Rapid Storage Technology driver using the 
    "F6" (Load Driver) installation method described in section 6.3 below.  The Intel(R) RST pre-OS version must support the Intel(R) RST technology that you are installing to.

c.  To install Intel(R) Rapid Storage Technology from within the OS during runtime, 
    double-click on the self-extracting and self-installing setup file and answer all
    prompts presented.

6.2 Intel(R) RST Windows Automated Installer*. Installation from HDD, USB, or CD-ROM
Note: This method is applicable to computers configured for RAID or AHCI mode.

a.  Obtain the Intel(R) Rapid Storage Technology setup file name: SetupRST.exe) and
    double-click to self-extract and to begin the setup process.

b.  The Welcome window appears. Click 'Next' to continue.

c.  For systems running in RAID mode, the Uninstallation Warning window appears. You will 
    not be able to uninstall the driver in this mode. Click 'Next' to continue.

d.  The Software License Agreement window appears. If you agree to these terms, click the
    check box then click 'Yes' to continue.

e.  Select the check box to install Intel(R) Optane(TM) Memory and Storage Management application if required then click 'Next' to continue.

f.  If the Windows Automated Installer* Wizard Complete window is shown without a prompt 
    to restart the system, click 'Finish' and proceed to step “g”. If it is shown with a 
    prompt to restart the system, select ‘I want to restart my computer now.' 
    (selected by default) and click 'Finish'. Once the system has restarted, proceed to 
    step “g”.

g.  To verify that the driver was loaded correctly, refer to section 7.

6.3 Pre-Installation of INTEL(R) RST driver using the "Load Driver" Method.

a.  Extract driver files from SetupRST.exe:
    - Open terminal in the directory with SetupRST.exe by right-clicking the directory
      and selecting "Open in Terminal" or "Open PowerShell here"
    - Enter the following command:
      ./SetupRST.exe -extractdrivers SetupRST_extracted
	  
b.  Copy all driver files from the SetupRST-extracted to a USB key media.

c.  For Microsoft Windows OS*:
    - During the operating system installation, after selecting the location to install 
      Windows, click 'Load Driver' to install a third party SCSI or RAID driver.

d.  When prompted, insert the USB media and press Enter.

e.  Follow the prompts and browse to the location of the installation files.  Select the 
    appropriate ‘.inf’ file (64 or 32 bit).  If a supported controller is detected there 
    will be no error message. Follow prompts to continue and complete the installation.


**************************************************************************
* 7.  VERIFYING INSTALLATION OF THE SOFTWARE
**************************************************************************

Verifying ‘Have Disk’, 'Load Driver', or ‘Unattended Installation’: 
Depending on your system configuration, refer to the appropriate sub-topic below:

7.1 VMD Platform series:

A.  Enter Device Manager once you are logged into Windows OS.    
B.  Expand the 'Storage Controllers' entry for Windows 10* or later.
C.  Right-click on Intel(R) RST VMD Controller.    
D.  Select 'Properties'.
E.  Select the 'Driver' tab and you should see the following items.
	- [Driver Provider] should be ‘Intel’
	- [Driver Version] should be the INTEL(R) RST driver version just installed
    If these 2 items are correct, then the installation was successful.



**************************************************************************
* 8.  ADVANCED INSTALLATION INSTRUCTIONS
**************************************************************************
********************
8.1a INTEL(R) RST INSTALLER (SetupRST.exe)- Setup Flags for INTEL(R) RST Installer:
********************
NOTE: Setup flags are NOT case sensitive (i.e. ‘a’ or ‘A’ is the same flag value)
	[ -help | -? ]
	Display this help.

	[ -report | -r ] <path>
	Changes the default log directory path.

	[ -silent | -s ]
	Does not display any setup dialogs (silent install).

	[ -nodriver | -nodrv ]
	Installs only Intel Optane® Optane™ Memory and Storage Management.

	[ -onlydriver ]
	Install only Intel® RST driver

	[ -accepteula ]
	This option is mandatory while silent install and means that you accept the End User License Agreement (EULA)
	Please read the EULA in the GUI installer before accepting it on the command line.

Notes:  Flags and their parameters are not case-sensitive. Flags may be supplied in any 
        order, with the exception of the -S and -G, which must be supplied last. When 
        using the -A flag, a target path may be specified via the -P flag, -G, -S, and -N 
        flags are ignored. When using the -P flags, there should be space between the flag 
        and the argument.

**************************************************************************
* 9.  IDENTIFYING THE SOFTWARE VERSION NUMBER
**************************************************************************
9.1 Use the following steps to identify the software version number following a ‘Have 
Disk’, 'Load Driver', or ‘unattended installation’.

9.1.VMD Platform Series: 

A.  Enter the 'Device Manager'.
B.  Expand the 'Storage Controllers' entry.
C.  Right-click on the Intel(R) RST VMD Controller present.
D.  Select 'Properties'.
E.  Select the 'Driver' tab.
F.  The software version should be displayed after 'Driver Version:'
	

9.2 Identify the software version for Windows* Automated Installer or 'Package for the 
    Web' Installations:
1.  Click Start.
2.  Locate and select 'Intel® Optane(TM) Memory and Storage Management'. 
3.  The Intel® Optane(TM) Memory and Storage Management application should launch.
4.  From the Help window, click 'About'. The software version is displayed. 
    
**************************************************************************
* 10.  UNINSTALLING THE SOFTWARE
**************************************************************************

10a. UNINSTALLATION OF NON-DRIVER COMPONENTS
The removal of this software from the system will render any SATA disks inaccessible by 
the operating system; therefore, the uninstallation procedure will only uninstall non-
critical components of this software (user interface, start menu links, etc.). To remove 
critical components, see section 10b. 

Use the following procedure to uninstall the software:
1.  On the Start menu, select Intel® Optane(TM) Memory and Storage Management App.
2.  Right-click the application name, and then click 'Uninstall'.
3.  The uninstall program will start. Click through the options for the uninstallation.


10b. UNINSTALLATION OF DRIVER COMPONENTS
!!!!!!!!!!! WARNING !!!!!!!!!! WARNING !!!!!!! WARNING !!!!!!!!! WARNING !!!!!!!!!
The removal of this software from the system could render any SATA or NVMe disks/volumes 
inaccessible by the operating system. Back-up any important data before completing these 
steps.

Note: If you experience any difficulties making these changes to the system BIOS, please 
contact the motherboard manufacturer or your place of purchase for assistance.
 
**************************************************************************
* 11.  ENTERING THE Pre-OS USER INTERFACE
**************************************************************************

UEFI Driver/BIOS
*****************************
  Use the following steps to enter the Intel(R) Rapid Storage Technology UEFI HII-
  compliant user interface (Note: the exact steps and location of the UI is OEM platform 
  dependent.  You must consult your platform manufacturer for these exact steps and 
  location of the Intel(R) RST UEFI HII UI):

    1. Boot the system.
    2. Press key required to enter the platform's system BIOS (e.g F2)
    3. Locate the ‘Intel(R) Rapid Storage Technology’ item wherever it is located in your 
       platform’s system BIOS menu and enter it to launch the ‘Intel(R) Rapid Storage 
       Technology’ text-based UEFI UI. At the top of the main page of the UI the version 
       is indicated in the following format:
        'Intel(R) RST ww.x.y.zzzz SATA Driver’


**************************************************************************
* 12.  Pre-OS STORAGE SUB-SYSTEM MANAGEMENT
**************************************************************************

UEFI Driver/BIOS HII
*****************************
The Intel(R) Rapid Storage Technology - UEFI UI provides pre-OS Storage sub-system 
management which enables the following capabilities:

I- RAID Volume Management
1. Create RAID Volume
   Use this option to create one or two RAID volumes.

2. Delete
   Click on a RAID volume then use this option to delete the RAID volume. The pre-OS 
   methods are the only end-user methods to delete a RAID volume that has the OS boot 
   files on it.

3. Reset to Non-RAID 
   Click on a RAID volume then click on a member disk then use this option to reset a RAID 
   member disk to a non-RAID pass-through disk.

4. Recovery Volume Options
   If a recovery volume is present, use this option to 
        a. Disable Continuous Update
        b. Enable Only Recovery Disk
        c. Enable Only Master Disk

II – Intel(R) Optane(TM) Memory Technology Management
1. ‘Deconcatenate’ Intel(R) Optane(TM) Memory Volume
   Use this option to disable Intel(R) Optane(TM) memory volume and return the system to a non-Accelerated 
   Pass-through configuration.
     a. [X] Checkbox to preserve user data upon deconcatenation; Checked is the default
     b. <No> Decision box to confirm deconcatenation action; Yes or No (No is default)
   
**************************************************************************
* 13.  OPTIONS TO RESET THE RAID VOLUME in the INTEL(R) RST Pre-OS UI's
**************************************************************************
WARNING!!!!!!!!!!!!!!WARNING!!!!!!!!!!!!WARNING!!!!!!!!!WARNING!!!!!!!!!!WARNING!!!!!!!!
Before completing any of the following steps, it is recommended you Backup any wanted 
data that is located on the RAID volumes being deleted or disks being reset to non-RAID

Intel(R) Rapid Storage Technology - pre-OS UI provides two methods for resetting the RAID 
volume:
    > Delete RAID Volume
    > Reset Disks to Non-RAID

   Differences between the options are noted below. Users are advised to select the option 
   based on the situation.

13.1 Delete RAID Volume
     When a RAID volume is deleted, RAID metadata on the participating disks is erased and 
     sector zero is cleared; as a result, the partition table and file system related data      
     are reset. Windows installer will not see any invalid data at the time of OS 
     installation. This is the recommended method for reconfiguring the RAID volume and 
     installing OS on it.

13.2 Reset Disks to Non-RAID
     This option is used to reset the metadata on the disk which participates in more than 
     one RAID volume in single operation. It should be used if 'Delete RAID Volume' option 
     fails for any reason and to reset a disk that has been marked as Spare and offline 
     member. When a disk in the RAID volume is reset to non-RAID, RAID metadata is erased. 
     However, partition table and file system related data still exists, which may be 
     invalid. This might cause Windows installer to misinterpret the information available 
     on the 'reset disk' at the time of installation. This could result in unexpected 
     behavior in OS installation.

**************************************************************************
* DISCLAIMER
**************************************************************************

INFORMATION IN THIS DOCUMENT IS PROVIDED IN CONNECTION WITH INTEL PRODUCTS. NO LICENSE, 
EXPRESS OR IMPLIED, BY ESTOPPEL OR OTHERWISE, TO ANY INTELLECTUAL PROPERTY RIGHTS IS 
GRANTED BY THIS DOCUMENT. EXCEPT AS PROVIDED IN INTEL'S TERMS AND CONDITIONS OF SALE FOR 
SUCH PRODUCTS, INTEL ASSUMES NO LIABILITY WHATSOEVER AND INTEL DISCLAIMS ANY EXPRESS
OR IMPLIED WARRANTY, RELATING TO SALE AND/OR USE OF INTEL PRODUCTS INCLUDING LIABILITY OR 
WARRANTIES RELATING TO FITNESS FOR A PARTICULAR PURPOSE, MERCHANTABILITY, OR INFRINGEMENT 
OF ANY PATENT, COPYRIGHT OR OTHER INTELLECTUAL PROPERTY RIGHT.

UNLESS OTHERWISE AGREED IN WRITING BY INTEL, THE INTEL PRODUCTS ARE NOT DESIGNED NOR 
INTENDED FOR ANY APPLICATION IN WHICH THE FAILURE OF THE INTEL PRODUCT COULD CREATE A 
SITUATION WHERE PERSONAL INJURY OR DEATH MAY OCCUR.

Intel may make changes to specifications and product descriptions at any time, without 
notice. Designers must not rely on the absence or characteristics of any features or 
instructions marked "reserved" or "undefined". Intel reserves these for future definition 
and shall have no responsibility whatsoever for conflicts or incompatibilities arising 
from future changes to them. The information here is subject to change without notice. Do 
not finalize a design with this information.

The products described in this document may contain design defects or errors known as 
errata which may cause the product to deviate from published specifications. Current 
characterized errata are available on request.

Contact your local Intel sales office or your distributor to obtain the latest 
specifications and before placing your product order.

Copies of documents which have an order number and are referenced in this document, or 
other Intel literature, may be obtained by calling 1-800-548-4725, or go to: 
http://www.intel.com/#/en_us_01

Intel(R) is a trademark of Intel Corporation or its subsidiaries in the U.S. and/or other countries.

* Other names and brands may be claimed as the property of others

Copyright (C) Intel Corporation. All rights reserved.

***************************************************************************
* INTEL SOFTWARE LICENSE AGREEMENT
***************************************************************************
DO NOT DOWNLOAD, INSTALL, ACCESS, COPY, OR USE ANY PORTION OF THE SOFTWARE UNTIL YOU HAVE READ AND ACCEPTED THE TERMS AND CONDITIONS OF THIS AGREEMENT. BY INSTALLING, COPYING, ACCESSING, OR USING THE SOFTWARE, YOU AGREE TO BE LEGALLY BOUND BY THE TERMS AND CONDITIONS OF THIS AGREEMENT. If You do not agree to be bound by, or the entity for whose benefit You act has not authorized You to accept, these terms and conditions, do not install, access, copy, or use the Software and destroy all copies of the Software in Your possession.

This SOFTWARE LICENSE AGREEMENT (this “Agreement”) is entered into between Intel Corporation, a Delaware corporation (“Intel”) and You. “You” refers to you or your employer or other entity for whose benefit you act, as applicable. If you are agreeing to the terms and conditions of this Agreement on behalf of a company or other legal entity, you represent and warrant that you have the legal authority to bind that legal entity to the Agreement, in which case, "You" or "Your" shall be in reference to such entity. Intel and You are referred to herein individually as a “Party” or, together, as the “Parties”.

The Parties, in consideration of the mutual covenants contained in this Agreement, and for other good and valuable consideration, the receipt and sufficiency of which they acknowledge, and intending to be legally bound, agree as follows: 

1. PURPOSE. You seek to obtain, and Intel desires to provide You, under the terms of this Agreement, Software solely for Your efforts to develop and distribute products integrating Intel hardware and Intel software. “Software” refers to certain software or other collateral, including, but not limited to, related components, operating system, application program interfaces, device drivers, associated media, printed or electronic documentation and any updates, upgrades or releases thereto associated with Intel product(s), software or service(s). “Intel-based product” refers to a device that includes, incorporates, or implements Intel product(s), software or service(s).

2. LIMITED LICENSE. Conditioned on Your compliance with the terms and conditions of this Agreement, Intel grants to You a limited, nonexclusive, nontransferable, revocable, worldwide, fully paid-up license during the term of this Agreement, without the right to sublicense, under Intel’s copyrights (subject to any third party licensing requirements), to (i) internally prepare derivative works (as defined in 17 U.S.C. § 101) of the Software (“Derivatives”), if provided or otherwise made available by Intel in source code form, and reproduce the Software, including Derivatives, in each case only for Your own internal evaluation, testing, validation, and development of Intel-based products and any associated maintenance thereof; (ii) reproduce, display, and publicly perform an object code representation of the Software, including Your Derivatives, in each case only when integrated with and executed by an Intel-based product, subject to any third party licensing requirements; and (iii) distribute an object code representation of the Software, provided by Intel, or of any Derivatives created by You, solely as embedded in or for execution on an Intel-based product, and if to an end user, pursuant to a license agreement with terms and conditions at least as restrictive as those contained in the Intel End User Software License Agreement in Appendix A hereto.

If You are not the final manufacturer or vendor of an Intel-based product incorporating or designed to incorporate the Software, You may transfer a copy of the Software, including any Derivatives (and related end user documentation) created by You to Your Original Equipment Manufacturer (OEM), Original Device Manufacturer (ODM), distributors, or system integration partners (“Your Partner”) for use in accordance with the terms and conditions of this Agreement, provided Your Partner agrees to be fully bound by the terms hereof and provided that You will remain fully liable to Intel for the actions and inactions of Your Partner(s).

3. LICENSE RESTRICTIONS. All right, title and interest in and to the Software and associated documentation are and will remain the exclusive property of Intel and its licensors or suppliers. Unless expressly permitted under the Agreement, You will not, and will not allow any third party to (i) use, copy, distribute, sell or offer to sell the Software or associated documentation; (ii) modify, adapt, enhance, disassemble, decompile, reverse engineer, change or create derivative works from the Software except and only to the extent as specifically required by mandatory applicable laws or any applicable third party license terms accompanying the Software; (iii) use or make the Software available for the use or benefit of third parties; or (iv) use the Software on Your products other than those that include the Intel hardware product(s), platform(s), or software identified in the Software; or (v) publish or provide any Software benchmark or comparison test results. You acknowledge that an essential basis of the bargain in this Agreement is that Intel grants You no licenses or other rights including, but not limited to, patent, copyright, trade secret, trademark, trade name, service mark or other intellectual property licenses or rights with respect to the Software and associated documentation, by implication, estoppel or otherwise, except for the licenses expressly granted above. You acknowledge there are significant uses of the Software in its original, unmodified and uncombined form. You may not remove any copyright notices from the Software.

4. LICENSE TO FEEDBACK. This Agreement does not obligate You to provide Intel with materials, information, comments, suggestions, Your Derivatives or other communication regarding the features, functions, performance or use of the Software (“Feedback”). If any portion of the Software is provided or otherwise made available by Intel in source code form, to the extent You provide Intel with Feedback in a tangible form, You grant to Intel and its affiliates a non-exclusive, perpetual, sublicenseable, irrevocable, worldwide, royalty-free, fully paid-up and transferable license, to and under all of Your intellectual property rights, whether perfected or not, to publicly perform, publicly display, reproduce, use, make, have made, sell, offer for sale, distribute, import, create derivative works of and otherwise exploit any comments, suggestions, descriptions, ideas, Your Derivatives or other feedback regarding the Software provided by You or on Your behalf.

5. OPEN SOURCE STATEMENT. The Software may include Open Source Software (OSS) licensed pursuant to OSS license agreement(s) identified in the OSS comments in the applicable source code file(s) or file header(s) provided with or otherwise associated with the Software. Neither You nor any OEM, ODM, customer, or distributor may subject any proprietary portion of the Software to any OSS license obligations including, without limitation, combining or distributing the Software with OSS in a manner that subjects Intel, the Software or any portion thereof to any OSS license obligation. Nothing in this Agreement limits any rights under, or grants rights that supersede, the terms of any applicable OSS license.

6. THIRD PARTY SOFTWARE. Certain third party software provided with or within the Software may only be used (a) upon securing a license directly from the owner of the software or (b) in combination with hardware components purchased from such third party and (c) subject to further license limitations by the software owner. A listing of any such third party limitations is in one or more text files accompanying the Software. You acknowledge Intel is not providing You with a license to such third party software and further that it is Your responsibility to obtain appropriate licenses from such third parties directly.

7. CONFIDENTIALITY. The terms and conditions of this Agreement, exchanged confidential information, as well as the Software are subject to the terms and conditions of the Non-Disclosure Agreement(s) or Intel Pre-Release Loan Agreement(s) (referred to herein collectively or individually as “NDA”) entered into by and in force between Intel and You, and in any case no less confidentiality protection than You apply to Your information of similar sensitivity. If You would like to have a contractor perform work on Your behalf that requires any access to or use of Software, You must obtain a written confidentiality agreement from the contractor which contains terms and conditions with respect to access to or use of Software no less restrictive than those set forth in this Agreement, excluding any distribution rights and use for any other purpose, and You will remain fully liable to Intel for the actions and inactions of those contractors. You may not use Intel's name in any publications, advertisements, or other announcements without Intel's prior written consent.

8. NO OBLIGATION; NO AGENCY. Intel may make changes to the Software, or items referenced therein, at any time without notice. Intel is not obligated to support, update, provide training for, or develop any further version of the Software or to grant any license thereto. No agency, franchise, partnership, joint-venture, or employee-employer relationship is intended or created by this Agreement.

9. EXCLUSION OF WARRANTIES. THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY EXPRESS OR IMPLIED WARRANTY OF ANY KIND INCLUDING WARRANTIES OF MERCHANTABILITY, NONINFRINGEMENT, OR FITNESS FOR A PARTICULAR PURPOSE. Intel does not warrant or assume responsibility for the accuracy or completeness of any information, text, graphics, links or other items within the Software.

10. LIMITATION OF LIABILITY. IN NO EVENT WILL INTEL OR ITS AFFILIATES, LICENSORS OR SUPPLIERS (INCLUDING THEIR RESPECTIVE DIRECTORS, OFFICERS, EMPLOYEES, AND AGENTS) BE LIABLE FOR ANY DAMAGES WHATSOEVER (INCLUDING, WITHOUT LIMITATION, LOST PROFITS, BUSINESS INTERRUPTION, OR LOST DATA) ARISING OUT OF OR IN RELATION TO THIS AGREEMENT, INCLUDING THE USE OF OR INABILITY TO USE THE SOFTWARE, EVEN IF INTEL HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. SOME JURISDICTIONS PROHIBIT EXCLUSION OR LIMITATION OF LIABILITY FOR IMPLIED WARRANTIES OR CONSEQUENTIAL OR INCIDENTAL DAMAGES, SO THE ABOVE LIMITATION MAY IN PART NOT APPLY TO YOU. THE SOFTWARE LICENSED HEREUNDER IS NOT DESIGNED OR INTENDED FOR USE IN ANY MEDICAL, LIFE SAVING OR LIFE SUSTAINING SYSTEMS, TRANSPORTATION SYSTEMS, NUCLEAR SYSTEMS, OR FOR ANY OTHER MISSION CRITICAL APPLICATION IN WHICH THE FAILURE OF THE SOFTWARE COULD LEAD TO PERSONAL INJURY OR DEATH. YOU MAY ALSO HAVE OTHER LEGAL RIGHTS THAT VARY FROM JURISDICTION TO JURISDICTION. THE LIMITED REMEDIES, WARRANTY DISCLAIMER AND LIMITED LIABILITY ARE FUNDAMENTAL ELEMENTS OF THE BASIS OF THE BARGAIN BETWEEN INTEL AND YOU. YOU ACKNOWLEDGE INTEL WOULD BE UNABLE TO PROVIDE THE SOFTWARE WITHOUT SUCH LIMITATIONS. YOU WILL INDEMNIFY AND HOLD INTEL AND ITS AFFILIATES, LICENSORS AND SUPPLIERS (INCLUDING THEIR RESPECTIVE DIRECTORS, OFFICERS, EMPLOYEES, AND AGENTS) HARMLESS AGAINST ALL CLAIMS, LIABILITIES, LOSSES, COSTS, DAMAGES, AND EXPENSES (INCLUDING REASONABLE ATTORNEY FEES), ARISING OUT OF, DIRECTLY OR INDIRECTLY, THE DISTRIBUTION OF THE SOFTWARE AND ANY CLAIM OF PRODUCT LIABILITY, PERSONAL INJURY OR DEATH ASSOCIATED WITH ANY UNINTENDED USE, EVEN IF SUCH CLAIM ALLEGES THAT INTEL OR AN INTEL AFFILIATE, LICENSORS OR SUPPLIER WAS NEGLIGENT REGARDING THE DESIGN OR MANUFACTURE OF THE SOFTWARE.

11. TERMINATION AND SURVIVAL. Intel may terminate this Agreement for any reason with thirty (30) days’ notice and immediately if You or someone acting on Your behalf or at Your behest violates any of its terms or conditions. Upon termination, You will immediately destroy and ensure the destruction of the Software or return all copies of the Software to Intel (including providing certification of such destruction or return back to Intel). Upon termination of this Agreement, all licenses granted to You hereunder terminate immediately. All Sections of this Agreement, except Section 2, will survive termination.

12. GOVERNING LAW AND JURISDICTION. This Agreement and any dispute arising out of or relating to it will be governed by the laws of the U.S.A. and Delaware, without regard to conflict of laws principles. The Parties exclude the application of the United Nations Convention on Contracts for the International Sale of Goods (1980). The state and federal courts sitting in Delaware, U.S.A. will have exclusive jurisdiction over any dispute arising out of or relating to this Agreement. The Parties consent to personal jurisdiction and venue in those courts. A Party that obtains a judgment against the other Party in the courts identified in this section may enforce that judgment in any court that has jurisdiction over the Parties.

13. EXPORT REGULATIONS/EXPORT CONTROL. You agree that neither You nor Your subsidiaries will export/re-export the Software, directly or indirectly, to any country for which the U.S. Department of Commerce or any other agency or department of the U.S. Government or the foreign government from where it is shipping requires an export license, or other governmental approval, without first obtaining any such required license or approval. In the event the Software is exported from the U.S.A. or re-exported from a foreign destination by You or Your subsidiary, You will ensure that the distribution and export/re-export or import of the Software complies with all laws, regulations, orders, or other restrictions of the U.S. Export Administration Regulations and the appropriate foreign government.

14. GOVERNMENT RESTRICTED RIGHTS. The Software is a commercial item (as defined in 48 C.F.R. 2.101) consisting of commercial computer software and commercial computer software documentation (as those terms are used in 48 C.F.R. 12.212). Consistent with 48 C.F.R. 12.212 and 48 C.F.R 227.7202-1 through 227.7202-4, You will not provide the Software to the U.S. Government. Contractor or Manufacturer is Intel Corporation, 2200 Mission College Blvd., Santa Clara, CA 95054.

15. ASSIGNMENT. You may not delegate, assign or transfer this Agreement, the license(s) granted or any of Your rights or duties hereunder, expressly, by implication, by operation of law, or otherwise and any attempt to do so, without Intel’s express prior written consent, will be null and void. Intel may assign, delegate and transfer this Agreement, and its rights and obligations hereunder, in its sole discretion.

16. ENTIRE AGREEMENT; SEVERABILITY. The terms and conditions of this Agreement and any NDA with Intel constitute the entire agreement between the parties with respect to the subject matter hereof, and merge and supersede all prior or contemporaneous agreements, understandings, negotiations and discussions. Neither Party will be bound by any terms, conditions, definitions, warranties, understandings, or representations with respect to the subject matter hereof other than as expressly provided herein. In the event any provision of this Agreement is unenforceable or invalid under any applicable law or applicable court decision, such unenforceability or invalidity will not render this Agreement unenforceable or invalid as a whole, instead such provision will be changed and interpreted so as to best accomplish the objectives of such provision within legal limits.

17. WAIVER. The failure of a Party to require performance by the other Party of any provision hereof will not affect the full right to require such performance at any time thereafter; nor will waiver by a Party of a breach of any provision hereof constitute a waiver of the provision itself.

18. PRIVACY. YOUR PRIVACY RIGHTS ARE SET FORTH IN INTEL’S PRIVACY NOTICE, WHICH FORMS A PART OF THIS AGREEMENT. PLEASE REVIEW THE PRIVACY NOTICE AT HTTP://WWW.INTEL.COM/PRIVACY TO LEARN HOW INTEL COLLECTS, USES AND SHARES INFORMATION ABOUT YOU.

APPENDIX A

INTEL END USER SOFTWARE LICENSE AGREEMENT

IMPORTANT - READ BEFORE COPYING, INSTALLING OR USING.

THE FOLLOWING NOTICE, OR TERMS AND CONDITIONS SUBSTANTIALLY IDENTICAL IN NATURE AND EFFECT, MUST APPEAR IN THE DOCUMENTATION ASSOCIATED WITH THE INTEL-BASED PRODUCT INTO WHICH THE SOFTWARE IS INSTALLED. MINIMALLY, SUCH NOTICE MUST APPEAR IN THE USER GUIDE FOR THE PRODUCT. THE TERM “LICENSEE” IN THIS TEXT REFERS TO THE END USER OF THE PRODUCT.

LICENSE. Licensee has a license under Intel’s copyrights to reproduce Intel’s Software only in its unmodified and binary form, (with the accompanying documentation, the “Software”) for Licensee’s personal use only, and not commercial use, in connection with Intel-based products for which the Software has been provided, subject to the following conditions:

(a)                Licensee may not disclose, distribute or transfer any part of the Software, and You agree to prevent unauthorized copying of the Software.

(b)               Licensee may not reverse engineer, decompile, or disassemble the Software.

(c)                Licensee may not sublicense the Software.

(d)               The Software may contain the software and other intellectual property of third party suppliers, some of which may be identified in, and licensed in accordance with, an enclosed license.txt file or other text or file.

(e)                Intel has no obligation to provide any support, technical assistance or updates for the Software.

OWNERSHIP OF SOFTWARE AND COPYRIGHTS. Title to all copies of the Software remains with Intel or its licensors or suppliers. The Software is copyrighted and protected by the laws of the United States and other countries, and international treaty provisions. Licensee may not remove any copyright notices from the Software. Except as otherwise expressly provided above, Intel grants no express or implied right under Intel patents, copyrights, trademarks, or other intellectual property rights. Transfer of the license terminates Licensee’s right to use the Software.

DISCLAIMER OF WARRANTY. The Software is provided “AS IS” without warranty of any kind, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION, WARRANTIES OF MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE.

LIMITATION OF LIABILITY. NEITHER INTEL NOR ITS LICENSORS OR SUPPLIERS WILL BE LIABLE FOR ANY LOSS OF PROFITS, LOSS OF USE, INTERRUPTION OF BUSINESS, OR INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES OF ANY KIND WHETHER UNDER THIS AGREEMENT OR OTHERWISE, EVEN IF INTEL HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

LICENSE TO USE COMMENTS AND SUGGESTIONS. This Agreement does NOT obligate Licensee to provide Intel with comments or suggestions regarding the Software. However, if Licensee provides Intel with comments or suggestions for the modification, correction, improvement or enhancement of (a) the Software or (b) Intel products or processes that work with the Software, Licensee grants to Intel a non-exclusive, worldwide, perpetual, irrevocable, transferable, royalty-free license, with the right to sublicense, under Licensee’s intellectual property rights, to incorporate or otherwise utilize those comments and suggestions.

TERMINATION OF THIS LICENSE. Intel or the sublicensor may terminate this license at any time if Licensee is in breach of any of its terms or conditions. Upon termination, Licensee will immediately destroy or return to Intel all copies of the Software.

THIRD PARTY BENEFICIARY. Intel is an intended beneficiary of the End User License Agreement and has the right to enforce all of its terms.

U.S. GOVERNMENT RESTRICTED RIGHTS. The Software is a commercial item (as defined in 48 C.F.R. 2.101) consisting of commercial computer software and commercial computer software documentation (as those terms are used in 48 C.F.R. 12.212), consistent with 48 C.F.R. 12.212 and 48 C.F.R 227.7202-1 through 227.7202-4. You will not provide the Software to the U.S. Government. Contractor or Manufacturer is Intel Corporation, 2200 Mission College Blvd., Santa Clara, CA 95054.

EXPORT LAWS. Licensee agrees that neither Licensee nor Licensee’s subsidiaries will export/re-export the Software, directly or indirectly, to any country for which the U.S. Department of Commerce or any other agency or department of the U.S. Government or the foreign government from where it is shipping requires an export license, or other governmental approval, without first obtaining any such required license or approval. In the event the Software is exported from the U.S.A. or re-exported from a foreign destination by Licensee, Licensee will ensure that the distribution and export/re-export or import of the Software complies with all laws, regulations, orders, or other restrictions of the U.S. Export Administration Regulations and the appropriate foreign government.

APPLICABLE LAWS. This Agreement and any dispute arising out of or relating to it will be governed by the laws of the U.S.A. and Delaware, without regard to conflict of laws principles. The Parties to this Agreement exclude the application of the United Nations Convention on Contracts for the International Sale of Goods (1980). The state and federal courts sitting in Delaware, U.S.A. will have exclusive jurisdiction over any dispute arising out of or relating to this Agreement. The Parties consent to personal jurisdiction and venue in those courts. A Party that obtains a judgment against the other Party in the courts identified in this section may enforce that judgment in any court that has jurisdiction over the Parties.

Licensee’s specific rights may vary from country to country.
# CALDERA-plugin for SOCBED

This plugin is intended to extend the functionality of the [SOCBED framework](https://github.com/fkie-cad/socbed) by enabling the user to execute the attack chain presented in [MITREs APT29 Attack Evaluation](https://attackevals.mitre-engenuity.org/enterprise/apt29/).
To achieve this, [CALDERA](https://github.com/mitre/caldera) is installed on the Attacker-VM and provided all necessary information - abilities, techniques and payloads.

## Installation

**WARNING**: The payloads used by APT29 contains several potentially malicous files.
Due to some problems with ansible, these are not yet encrypted, so be aware that your anti-virus software of choice might sound the alarm.


This plugin is intended to be used with SOCBED v1.1.3.
Using another version may or may not have unintended side effects.
```sh
# Clone this repository
git clone git@github.com:Maspital/socbed-caldera.git

# Run the installation script, providing the path to your socbed directory
./socbed-caldera/install_plugin /socbed/directory/
```

## Usage

tbd

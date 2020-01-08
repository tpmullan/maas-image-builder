$ErrorActionPreference = "Stop"

function WaitForNetwork ($seconds) {
    while (1) {
        # Get a list of DHCP-enabled interfaces that have a
        # non-$null DefaultIPGateway property.
        $x = gwmi -class Win32_NetworkAdapterConfiguration `
            -filter DHCPEnabled=TRUE |
                where { $_.DefaultIPGateway -ne $null }

        # If there is (at least) one available, exit the loop.
        if ( ($x | measure).count -gt 0 ) {
            break
        }

        # If $seconds > 0 and we have tried $seconds times without
        # success, throw an exception.
        if ( $seconds -gt 0 -and $try++ -ge $seconds ) {
            throw "Network unavaiable after $try seconds."
        }

        # Wait one second.
        start-sleep -s 1
    }
}

try
{
    # Need to have network connection to continue, wait a maximum of 60
    # seconds for the network to be active.
    WaitForNetwork 60

    # Install PSWindowsUpdate modules for PowerShell
    if (!(Test-Path -Path "$ENV:SystemRoot\System32\WindowsPowerShell\v1.0\Modules\PSWindowsUpdate"))
    {
        $Host.UI.RawUI.WindowTitle = "Installing PSWindowsUpdate..."
        Copy-Item E:\PSWindowsUpdate $ENV:SystemRoot\System32\WindowsPowerShell\v1.0\Modules -recurse
    }

    # Start the Update process.
    Import-Module PSWindowsUpdate
    $Host.UI.RawUI.WindowTitle = "Installing updates..."
    Get-WUInstall -AcceptAll -IgnoreReboot -IgnoreUserInput -NotCategory "Language packs"
    if (Get-WURebootStatus -Silent)
    {
        $Host.UI.RawUI.WindowTitle = "Updates installation finished. Rebooting."
        shutdown /r /t 0
    }
    else
    {
        $osArch = (Get-WmiObject  Win32_OperatingSystem).OSArchitecture
        if($osArch.StartsWith("64"))
        {
            $archDir = "x64"
            $programFilesDir = ${ENV:ProgramFiles(x86)}
        }
        else
        {
            $archDir = "x86"
            $programFilesDir = $ENV:ProgramFiles
        }

        # Inject extra drivers if the infs directory is present on the attached iso
        if (Test-Path -Path "E:\infs")
        {
            # To install extra drivers the Windows Driver Kit is needed for dpinst.exe.
            # Sadly you cannot just download dpinst.exe. The whole driver kit must be
            # installed.

            # Download the WDK installer.
            $Host.UI.RawUI.WindowTitle = "Downloading Windows Driver Kit..."
            $webclient = New-Object System.Net.WebClient
            $wdksetup = [IO.Path]::GetFullPath("$ENV:TEMP\wdksetup.exe")
            $wdkurl = "http://download.microsoft.com/download/0/8/C/08C7497F-8551-4054-97DE-60C0E510D97A/wdk/wdksetup.exe"
            $webclient.DownloadFile($wdkurl, $wdksetup)

            # Run the installer.
            $Host.UI.RawUI.WindowTitle = "Installing Windows Driver Kit..."
            $p = Start-Process -PassThru -Wait -FilePath "$wdksetup" -ArgumentList "/features OptionId.WindowsDriverKitComplete /q /ceip off /norestart"
            if ($p.ExitCode -ne 0)
            {
                throw "Installing $wdksetup failed."
            }

            # Run dpinst.exe with the path to the drivers.
            $Host.UI.RawUI.WindowTitle = "Injecting Windows drivers..."
            $dpinst = "$programFilesDir\Windows Kits\8.1\redist\DIFx\dpinst\EngMui\$archDir\dpinst.exe"
            Start-Process -Wait -FilePath "$dpinst" -ArgumentList "/S /C /F /SA /Path E:\infs"

            # Uninstall the WDK
            $Host.UI.RawUI.WindowTitle = "Uninstalling Windows Driver Kit..."
            Start-Process -Wait -FilePath "$wdksetup" -ArgumentList "/features + /q /uninstall /norestart"
        }

        $Host.UI.RawUI.WindowTitle = "Installing Cloudbase-Init..."
        $cloudbaseInitPath = "E:\cloudbase\cloudbase_init.msi"
        $cloudbaseInitLog = "$ENV:Temp\cloudbase_init.log"
        $serialPortName = @(Get-WmiObject Win32_SerialPort)[0].DeviceId
        $p = Start-Process -Wait -PassThru -FilePath msiexec -ArgumentList "/i $cloudbaseInitPath /qn /l*v $cloudbaseInitLog LOGGINGSERIALPORTNAME=$serialPortName"
        if ($p.ExitCode -ne 0)
        {
            throw "Installing $cloudbaseInitPath failed. Log: $cloudbaseInitLog"
        }

        # We're done, remove LogonScript and disable AutoLogon
        Remove-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name Unattend*
        Remove-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name AutoLogonCount

        $Host.UI.RawUI.WindowTitle = "Running SetSetupComplete..."
        & "$ENV:ProgramFiles\Cloudbase Solutions\Cloudbase-Init\bin\SetSetupComplete.cmd"

        # Write success, this is used to check that this process made it this far
        New-Item -Path C:\success.tch -Type file -Force

        $Host.UI.RawUI.WindowTitle = "Running Sysprep..."
        $unattendedXmlPath = "$ENV:ProgramFiles\Cloudbase Solutions\Cloudbase-Init\conf\Unattend.xml"
        & "$ENV:SystemRoot\System32\Sysprep\Sysprep.exe" `/generalize `/oobe `/shutdown `/unattend:"$unattendedXmlPath"
    }
}
catch
{
    $_ | Out-File C:\error_log.txt
    shutdown /s /f /t 0
}

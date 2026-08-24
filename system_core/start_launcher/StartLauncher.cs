using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Principal;
using System.Text;
using System.Windows.Forms;

internal static class StartLauncher
{
    private const string LauncherFileName = "launcher_gui.cmd";

    [STAThread]
    private static int Main()
    {
        try
        {
            string root = ResolveRoot();
            string launcher = Path.Combine(root, LauncherFileName);
            if (!File.Exists(launcher))
            {
                MessageBox.Show(
                    LauncherFileName + " was not found next to Start.exe.",
                    StartLauncherConfig.AppName,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 2;
            }

            string commandProcessor = Environment.GetEnvironmentVariable("ComSpec");
            if (string.IsNullOrWhiteSpace(commandProcessor))
            {
                commandProcessor = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.System),
                    "cmd.exe");
            }

            string icon = Path.Combine(root, "system_core", "icons", "app.ico");
            var process = ShouldElevate()
                ? BuildElevatedProcess(commandProcessor, root, launcher, icon)
                : BuildNormalProcess(commandProcessor, root, launcher, icon);

            Process.Start(process);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.Message,
                StartLauncherConfig.AppName,
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
    }

    private static ProcessStartInfo BuildNormalProcess(string commandProcessor, string root, string launcher, string icon)
    {
        var process = new ProcessStartInfo
        {
            FileName = commandProcessor,
            Arguments = "/d /c call \"" + launcher + "\"",
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };

        process.EnvironmentVariables["AUDION_APP_NAME"] = StartLauncherConfig.AppName;
        process.EnvironmentVariables["AUDION_APP_ID"] = StartLauncherConfig.AppId;
        if (File.Exists(icon))
        {
            process.EnvironmentVariables["AUDION_APP_ICON"] = icon;
        }
        return process;
    }

    private static ProcessStartInfo BuildElevatedProcess(string commandProcessor, string root, string launcher, string icon)
    {
        string buildDir = Path.Combine(root, "work", "start_launcher");
        Directory.CreateDirectory(buildDir);
        string elevatedScript = Path.Combine(buildDir, "StartElevated.cmd");

        var script = new StringBuilder();
        script.AppendLine("@echo off");
        script.AppendLine("chcp 65001 >nul");
        script.AppendLine("setlocal EnableExtensions");
        script.AppendLine(BatchSet("AUDION_APP_NAME", StartLauncherConfig.AppName));
        script.AppendLine(BatchSet("AUDION_APP_ID", StartLauncherConfig.AppId));
        script.AppendLine(BatchSet("AUDION_GUI_ELEVATE", "1"));
        if (File.Exists(icon))
        {
            script.AppendLine(BatchSet("AUDION_APP_ICON", icon));
        }
        script.AppendLine("call \"" + launcher + "\"");
        script.AppendLine("exit /b %ERRORLEVEL%");
        File.WriteAllText(elevatedScript, script.ToString(), new UTF8Encoding(false));

        return new ProcessStartInfo
        {
            FileName = commandProcessor,
            Arguments = "/d /c call \"" + elevatedScript + "\"",
            WorkingDirectory = root,
            UseShellExecute = true,
            Verb = "runas",
            WindowStyle = ProcessWindowStyle.Hidden,
        };
    }

    private static string BatchSet(string name, string value)
    {
        return "set \"" + name + "=" + (value ?? string.Empty).Replace("\"", "'") + "\"";
    }

    private static bool ShouldElevate()
    {
        if (IsEnvEnabled("AUDION_GUI_NO_ELEVATE"))
        {
            return false;
        }
        return (StartLauncherConfig.RequireAdministrator || IsEnvEnabled("AUDION_GUI_ELEVATE"))
            && !IsRunningAsAdministrator();
    }

    private static bool IsEnvEnabled(string name)
    {
        string value = Environment.GetEnvironmentVariable(name);
        return string.Equals(value, "1", StringComparison.OrdinalIgnoreCase)
            || string.Equals(value, "true", StringComparison.OrdinalIgnoreCase)
            || string.Equals(value, "yes", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsRunningAsAdministrator()
    {
        try
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                var principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
        }
        catch
        {
            return false;
        }
    }

    private static string ResolveRoot()
    {
        string location = Assembly.GetExecutingAssembly().Location;
        string directory = Path.GetDirectoryName(location);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            return directory;
        }
        return Environment.CurrentDirectory;
    }
}

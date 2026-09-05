import platform

from PySide6.QtCore import QLocale
from qfluentwidgets import QConfig, ConfigItem, BoolValidator, OptionsValidator, OptionsConfigItem, qconfig
import os

from src.core.utils import prog_path

config_file = os.path.abspath(os.path.join(prog_path, 'bin', "settings.json"))


class Config(QConfig):
    """ 应用配置类 """
    allLanguages = [i for i in os.listdir(os.path.join(prog_path, 'bin', 'languages')) if i.endswith(".qm")]
    allLanguagesHum = [QLocale(i[4:-3]).nativeLanguageName() for i in allLanguages]
    tool_bin = os.path.join(prog_path, 'bin', platform.system(), platform.machine())
    module_dir = os.path.join(prog_path, "bin", "module")
    workingFolder = ConfigItem("Tool", "WorkingFolder", prog_path)
    Version = ConfigItem("Tool", "Version", "5.0.0-prewiew")
    pluginRepo = ConfigItem("Tool", "pluginRepo", "https://raw.githubusercontent.com/ColdWindScholar/MPK_Plugins/main/")
    updateURL = ConfigItem("Tool", "updateURL", "https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest")
    language = OptionsConfigItem(
        "Tool", "Language", "English", OptionsValidator(allLanguages), restart=True)
    aiEngine = ConfigItem("Tool", 'AiEngine', False, BoolValidator())
    currentProjectName = ConfigItem("Tool", 'currentProjectName', "")
    selinuxPatch = ConfigItem("Tool", 'selinuxPatch', False, BoolValidator())
    autoUnpack = ConfigItem("Tool", 'autoUnpack', False, BoolValidator())
    checkUpdate = ConfigItem("Tool", 'checkUpdate', False, BoolValidator())
    projectStructure = OptionsConfigItem("Tool", "ProjectStructure", "Single", OptionsValidator(['Single', "Split"]))
    cpioImpl = OptionsConfigItem("Tool", "CpioImpl", "Native", OptionsValidator(['Native', "Python"]))

config = Config()
qconfig.load(config_file, config)
cfg = config

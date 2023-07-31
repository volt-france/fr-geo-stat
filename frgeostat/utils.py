import tomllib as tl
from pathlib import Path
from rich.console import Console
from addict import Addict


cout = Console()
cerr = Console()

SITE_ROOT = "https://bureaux-vote.v.olt.sh"

Pkg = Path(__file__).parent
ConfigFile = Pkg / 'config.toml'

class Config:
    def __init__(self) -> None:
        self.file = ConfigFile
        self.data = Addict(tl.loads(self.file.read_text()))
    
    def from_alias(self, name: str) -> str:
        for fullname, aliases in self.data.aliases.items():
            for alias in aliases:
                if alias in name.lower() or name.lower() in alias:
                    return fullname
            
    def all(self):
        return self.data
        
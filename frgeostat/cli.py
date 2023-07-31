import typer
from typing import List, Optional
from itertools import cycle

from .utils import cerr, cout, Path, Pkg, Config
from .communes import Communes
from .departements import Departements


colors = cycle(['red', 'green', 'yellow', 'blue', 'magenta'])


app = typer.Typer(
    name="fr-geo-stat",
    help="Geospatial statistics about France and politics.",
    no_args_is_help=True
)


@app.command("build", help="Build a map, kind should be specified", no_args_is_help=True)
def build(
        kind: Optional[List[str]] = typer.Option(None, '-k', '--kind', help="The kind of map to build, can be several by repeating the flag each time."),
        out: Optional[List[str]] = typer.Option(None, '-o', '--out', help="The file path pointing where the map should be stored."),
    ):
    config = Config()
    
    for kd, ot in zip(kind, out):
        c = next(colors)
        kind = config.from_alias(kd)
        cout.log(f"[{c}]Map kind:[/{c}] {kd} -> [yellow]{kind}[/yellow]")
        if kind == 'commune':
            co = Communes()
            co.transform()
            p = Path(ot)
            d = p.parent if p.is_file() else ''
            if d:
                d.mkdir(parents=True, exist_ok=True)
                cout.log(f"[yellow]Created directory: [dim]{d}[/dim][/yellow]")
            p = p if p.is_file() else d / 'communes.score.map.html' if d else p
            co.build().save(str(p))
        elif kind == 'departement':
            dept = Departements()
            dept.transform()
            p = Path(ot)
            d = p.parent if p.is_file() else ''
            if d:
                d.mkdir(parents=True, exist_ok=True)
                cout.log(f"[yellow]Created directory: [dim]{d}[/dim][/yellow]")
            p = p if p.is_file() else d / 'communes.score.map.html' if d else p
            dept.build().save(str(p))
            
        else:
            cout.log("[red]Error:[/red] Incorrect kind of map, exiting..")
            typer.Exit(1)
    

@app.command("ls", help="List the kinds of map this toolbox can build.")
def list_maps(
        what: str = typer.Argument(None, help="What should be listed")
    ):
    config = Config()
    if what is None:
        what = 'zone'
        
    for i,option in enumerate(config.data[what]):
        c = next(colors)
        cout.print(f"[bold {c}]({i})[/bold {c}] [{c}]{option}[/{c}]")
    
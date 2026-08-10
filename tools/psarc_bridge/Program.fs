open System
open System.IO
open System.Text.Json
open Rocksmith2014.Common
open Rocksmith2014.Conversion
open Rocksmith2014.PSARC
open Rocksmith2014.XML

[<Literal>]
let UpstreamCommit = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"

let private isBassSng (path: string) =
    let name = Path.GetFileNameWithoutExtension(path)
    name.Contains("_bass", StringComparison.OrdinalIgnoreCase)
    && not (name.Contains("vocals", StringComparison.OrdinalIgnoreCase))

let private containsIgnoreCase (needle: string) (value: string) =
    value.Contains(needle, StringComparison.OrdinalIgnoreCase)

let private inspectPackage (psarcPath: string) =
    use psarc = PSARC.OpenFile(psarcPath)
    let entries = psarc.Manifest |> List.sort
    let bassSng = entries |> List.filter (fun p -> p.EndsWith(".sng", StringComparison.OrdinalIgnoreCase) && isBassSng p)
    let manifests = entries |> List.filter (fun p -> p.EndsWith(".json", StringComparison.OrdinalIgnoreCase) && containsIgnoreCase "manifest" p)
    let audioWem = entries |> List.filter (fun p -> p.EndsWith(".wem", StringComparison.OrdinalIgnoreCase))
    let soundBanks = entries |> List.filter (fun p -> p.EndsWith(".bnk", StringComparison.OrdinalIgnoreCase))
    let xblocks = entries |> List.filter (fun p -> p.EndsWith(".xblock", StringComparison.OrdinalIgnoreCase))
    let albumArt = entries |> List.filter (fun p -> p.EndsWith(".dds", StringComparison.OrdinalIgnoreCase) && containsIgnoreCase "album" p)
    let payload =
        {| upstreamCommit = UpstreamCommit
           entryCount = entries.Length
           entries = entries
           bassSng = bassSng
           manifests = manifests
           audioWem = audioWem
           soundBanks = soundBanks
           xblocks = xblocks
           albumArt = albumArt |}
    Console.Out.Write(JsonSerializer.Serialize(payload))

let private importPackage (psarcPath: string) (extractionDirectory: string) =
    Directory.CreateDirectory extractionDirectory |> ignore
    let platform = Platform.fromPackageFileName psarcPath
    use psarc = PSARC.OpenFile(psarcPath)

    let xblocks =
        psarc.Manifest
        |> List.filter (fun path -> path.EndsWith(".xblock", StringComparison.OrdinalIgnoreCase))

    if xblocks.Length <> 1 then
        failwith $"Expected exactly one xblock in selected PSARC, found {xblocks.Length}. Song packs are not supported."

    psarc.ExtractFiles(extractionDirectory).GetAwaiter().GetResult()

    let bassSngPaths =
        Directory.GetFiles(extractionDirectory, "*.sng", SearchOption.AllDirectories)
        |> Array.filter isBassSng

    if bassSngPaths.Length = 0 then
        failwith "Selected PSARC contains no Bass SNG arrangement."

    let bassXmlPaths =
        bassSngPaths
        |> Array.mapi (fun index sngPath ->
            let targetPath = Path.Combine(extractionDirectory, $"arr_bass_{index}_RS2.xml")
            ConvertInstrumental.sngFileToXml sngPath targetPath platform
            |> Async.RunSynchronously

            let xml = InstrumentalArrangement.Load(targetPath)
            xml.MetaData.Arrangement <- "Bass"
            xml.Save(targetPath)
            targetPath)

    let payload =
        {| upstreamCommit = UpstreamCommit
           extractedDirectory = extractionDirectory
           bassXmlPaths = bassXmlPaths |}

    Console.Out.Write(JsonSerializer.Serialize(payload))

[<EntryPoint>]
let main argv =
    try
        if argv.Length = 2 && argv[0].Equals("inspect", StringComparison.OrdinalIgnoreCase) then
            inspectPackage (Path.GetFullPath argv[1])
            0
        elif argv.Length = 2 then
            importPackage (Path.GetFullPath argv[0]) (Path.GetFullPath argv[1])
            0
        else
            eprintfn "Usage: RocksmithPsarcBridge <package.psarc> <extraction-directory> | RocksmithPsarcBridge inspect <package.psarc>"
            2
    with ex ->
        eprintfn "%s" ex.Message
        1

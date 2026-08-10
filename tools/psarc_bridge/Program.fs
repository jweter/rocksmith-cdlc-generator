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

[<EntryPoint>]
let main argv =
    try
        if argv.Length <> 2 then
            eprintfn "Usage: RocksmithPsarcBridge <package.psarc> <extraction-directory>"
            2
        else
            let psarcPath = Path.GetFullPath argv[0]
            let extractionDirectory = Path.GetFullPath argv[1]
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

                    // SNG conversion without manifest metadata preserves the musical
                    // arrangement but leaves the arrangement name blank. The bridge
                    // selected this SNG from the package's Bass filename contract, so
                    // set only that identity field before handing XML to Python.
                    let xml = InstrumentalArrangement.Load(targetPath)
                    xml.MetaData.Arrangement <- "Bass"
                    xml.Save(targetPath)
                    targetPath)

            let payload =
                {| upstreamCommit = UpstreamCommit
                   extractedDirectory = extractionDirectory
                   bassXmlPaths = bassXmlPaths |}

            Console.Out.Write(JsonSerializer.Serialize(payload))
            0
    with ex ->
        eprintfn "%s" ex.Message
        1

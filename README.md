# ~/ecossistema

    bin/llm.py          gateway unico de modelos (local e nuvem), com contexto dimensionado e sem truncamento silencioso
    bin/inventario.py   levanta o estado real da maquina e grava config/registro.json
    config/papeis.json  qual modelo cumpre qual papel, com o teste que justifica a escolha
    config/registro.json  ultimo inventario (versionado: o historico mostra o que mudou e quando)
    mcp/                servidores MCP (a unificar com as copias do Windows)
    CLAUDE.md           regras de orquestracao para qualquer agente

    bin/converter.py    PDF/DOCX/PPTX/XLSX/HTML -> Markdown (Docling, receita do lote L20, cache por hash, marcadores de pagina)

    bin/indice.py       indice semantico local do acervo (indexar, buscar, validar)
    bench/bench.py      bateria de avaliacao de modelos com autoteste

Pendentes: deduplicacao de versoes gemeas no indice; busca hibrida (palavra-chave + significado).

"""Servidor estático local para desenvolvimento, sem cache nenhum.

Usado só para testar a aplicação (ver CLAUDE.md, seção "Como testar"). O
`http.server` padrão do Python deixa o navegador decidir se reaproveita uma
resposta antiga; aqui forçamos `Cache-Control: no-store` em tudo, para nunca
mais depender de hard refresh durante o desenvolvimento.
"""

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


class SemCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    HTTPServer(("", porta), SemCacheHandler).serve_forever()

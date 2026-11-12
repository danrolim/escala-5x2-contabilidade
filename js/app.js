const NOMES_DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
const IDB_NOME = "escala-app-db";
const IDB_STORE = "arquivos";
const MODULOS_PYTHON = ["regras", "gerador_escala", "validador", "persistencia", "ponte"];

let pyodide = null;
let ponte = null;
let turnos = [];
let funcionarios = [];
let turnoContador = 1;
let funcionarioContador = 1;
let ultimaEscala = null;

function escapeHtml(texto) {
  if (texto === null || texto === undefined) return "";
  return String(texto)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatarHorasMinutos(horasDecimais) {
  const totalMinutos = Math.round(horasDecimais * 60);
  const h = Math.floor(totalMinutos / 60);
  const m = totalMinutos % 60;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}min`;
}

function jornadaDiariaPadrao(cargaHorariaSemanal) {
  const carga = Number(cargaHorariaSemanal) || 0;
  return Math.round((carga / 5) * 100) / 100;
}

function calcularProximoContador(lista) {
  let maior = 0;
  lista.forEach((item) => {
    const n = parseInt(String(item.id).replace(/\D/g, ""), 10);
    if (!isNaN(n) && n > maior) maior = n;
  });
  return maior + 1;
}

function baixarArquivo(nome, conteudo, tipo) {
  const blob = new Blob([conteudo], { type: tipo });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}

function abrirIndexedDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NOME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(IDB_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(chave) {
  const db = await abrirIndexedDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readonly");
    const req = tx.objectStore(IDB_STORE).get(chave);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

async function idbSet(chave, valor) {
  const db = await abrirIndexedDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readwrite");
    tx.objectStore(IDB_STORE).put(valor, chave);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function persistirBanco() {
  try {
    const bytes = pyodide.FS.readFile("/escala.db");
    await idbSet("escala.db", bytes);
  } catch (erro) {
    console.error("Falha ao persistir o banco no IndexedDB:", erro);
  }
}

function nomeExibicaoTurno(turno) {
  const nome = (turno.nome || "").trim();
  if (nome) return nome;
  const indice = turnos.indexOf(turno);
  return `Turno ${indice + 1}`;
}

function atualizarJornadaDiariaEstimada() {
  const carga = document.getElementById("carga-horaria").value;
  document.getElementById("jornada-diaria-estimada").textContent = formatarHorasMinutos(jornadaDiariaPadrao(carga));
}

function renderTurnos() {
  const container = document.getElementById("lista-turnos");
  container.innerHTML = "";
  turnos.forEach((turno, indice) => {
    const div = document.createElement("div");
    div.className = "linha-item";
    div.dataset.turnoId = turno.id;
    div.innerHTML = `
      <div class="campo">
        <label>Nome do turno</label>
        <input type="text" class="turno-nome" value="${escapeHtml(turno.nome)}" placeholder="Turno ${indice + 1}" />
      </div>
      <div class="campo">
        <label><input type="checkbox" class="turno-revezamento" ${turno.revezamento ? "checked" : ""} /> Revezamento (mín. 2 por turno)</label>
      </div>
      <button type="button" class="perigo secundario btn-remover-turno">Remover</button>
    `;
    container.appendChild(div);
  });
}

function renderFuncionarios() {
  const container = document.getElementById("lista-funcionarios");
  container.innerHTML = "";
  funcionarios.forEach((f, indice) => {
    const div = document.createElement("div");
    div.className = "linha-item";
    div.dataset.funcionarioId = f.id;
    const checkboxesTurnos = turnos
      .map(
        (t) => `
      <label><input type="checkbox" class="chk-turno-funcionario" value="${t.id}"
        ${f.turnosPermitidos.includes(t.id) ? "checked" : ""} /> ${escapeHtml(nomeExibicaoTurno(t))}</label>
    `
      )
      .join("");
    div.innerHTML = `
      <div class="campo">
        <label>Nome</label>
        <input type="text" class="funcionario-nome" value="${escapeHtml(f.nome)}" placeholder="Ex.: F${indice + 1} (se vazio, assume F${indice + 1})" />
      </div>
      <div class="campo">
        <label>Sexo</label>
        <select class="funcionario-sexo">
          <option value="M" ${f.sexo === "M" ? "selected" : ""}>Masculino</option>
          <option value="F" ${f.sexo === "F" ? "selected" : ""}>Feminino</option>
        </select>
      </div>
      <div class="campo">
        <label>Turnos em que pode atuar</label>
        <div class="checkbox-turnos">${checkboxesTurnos || "<em>Cadastre turnos acima</em>"}</div>
      </div>
      <button type="button" class="perigo secundario btn-remover-funcionario">Remover</button>
    `;
    container.appendChild(div);
  });
}

function atualizarResumoFuncionarios() {
  const total = funcionarios.length;
  const homens = funcionarios.filter((f) => f.sexo === "M").length;
  const mulheres = funcionarios.filter((f) => f.sexo === "F").length;
  document.getElementById(
    "resumo-funcionarios"
  ).textContent = `Total: ${total} funcionário(s) — ${homens} homem(ns), ${mulheres} mulher(es).`;
}

function turnoDoFuncionarioNoDia(semana, funcionarioId, dia) {
  const turnosNoDia = semana.turnos[dia] || semana.turnos[String(dia)] || {};
  for (const turnoId of Object.keys(turnosNoDia)) {
    if (turnosNoDia[turnoId].includes(funcionarioId)) return turnoId;
  }
  return "folga";
}

function montarEmpresaPayload() {
  const cargaHorariaSemanal = parseFloat(document.getElementById("carga-horaria").value);
  const horasPorDiaPadrao = jornadaDiariaPadrao(cargaHorariaSemanal);
  return {
    nome: document.getElementById("nome-empresa").value.trim(),
    setor: document.getElementById("setor-empresa").value,
    fase_lei: document.getElementById("fase-lei").value,
    carga_horaria_semanal: cargaHorariaSemanal,
    dias_funcionamento: diasFuncionamentoAtuais(),
    turnos: turnos.map((t) => ({
      id: t.id,
      nome: nomeExibicaoTurno(t),
      horas_por_dia: horasPorDiaPadrao,
      revezamento: t.revezamento,
    })),
  };
}

function nomeExibicaoFuncionario(funcionario) {
  const nome = (funcionario.nome || "").trim();
  if (nome) return nome;
  const indice = funcionarios.indexOf(funcionario);
  return `F${indice + 1}`;
}

function montarFuncionariosPayload() {
  return funcionarios.map((f) => ({
    id: f.id,
    nome: nomeExibicaoFuncionario(f),
    sexo: f.sexo,
    turnos_permitidos: f.turnosPermitidos,
  }));
}

function diasFuncionamentoAtuais() {
  return Array.from(document.querySelectorAll(".chk-dia:checked"))
    .map((c) => parseInt(c.value, 10))
    .sort((a, b) => a - b);
}

function diasExibidosNaEscala() {
  // Sempre mostra a semana inteira (0 a 6), mesmo nos dias em que a empresa
  // não funciona, para deixar explícito onde há folga/trabalho em cada dia.
  return [0, 1, 2, 3, 4, 5, 6];
}

function renderEscala(escala) {
  const diasFuncionamento = diasFuncionamentoAtuais();
  const diasExibidos = diasExibidosNaEscala();
  const container = document.getElementById("container-escala");
  container.innerHTML = "";

  escala.semanas.forEach((semana, idxSemana) => {
    const titulo = document.createElement("div");
    titulo.className = "semana-titulo";
    titulo.textContent = `Semana ${idxSemana + 1} de ${escala.ciclo_semanas}`;
    container.appendChild(titulo);

    const tabela = document.createElement("table");
    tabela.dataset.semana = idxSemana;
    const thead = document.createElement("thead");
    const linhaCab = document.createElement("tr");
    linhaCab.innerHTML =
      "<th>Funcionário</th>" +
      diasExibidos.map((d) => `<th data-dia="${d}">${NOMES_DIAS[d]}</th>`).join("");
    thead.appendChild(linhaCab);
    tabela.appendChild(thead);

    const tbody = document.createElement("tbody");
    funcionarios.forEach((f) => {
      const tr = document.createElement("tr");
      let celulas = `<td class="celula-nome" data-funcionario-id="${f.id}">${escapeHtml(
        nomeExibicaoFuncionario(f)
      )}</td>`;
      diasExibidos.forEach((dia) => {
        if (!diasFuncionamento.includes(dia)) {
          celulas += `<td title="Empresa não funciona neste dia">Folga</td>`;
          return;
        }
        const valorAtual = turnoDoFuncionarioNoDia(semana, f.id, dia);
        const opcoes = [
          `<option value="folga" ${valorAtual === "folga" ? "selected" : ""}>Folga</option>`,
        ].concat(
          turnos.map(
            (t) =>
              `<option value="${t.id}" ${valorAtual === t.id ? "selected" : ""}>${escapeHtml(
                nomeExibicaoTurno(t)
              )}</option>`
          )
        );
        celulas += `<td><select class="celula-escala" data-semana="${idxSemana}" data-funcionario-id="${f.id}" data-dia="${dia}">${opcoes.join(
          ""
        )}</select></td>`;
      });
      tr.innerHTML = celulas;
      tbody.appendChild(tr);
    });
    tabela.appendChild(tbody);
    container.appendChild(tabela);
  });
}

function reconstruirEscalaDoDOM() {
  const diasFuncionamento = diasFuncionamentoAtuais();
  ultimaEscala.semanas.forEach((semana, idxSemana) => {
    const novasFolgas = {};
    const novosTurnos = {};
    diasFuncionamento.forEach((dia) => {
      novosTurnos[dia] = {};
      turnos.forEach((t) => {
        novosTurnos[dia][t.id] = [];
      });
    });
    funcionarios.forEach((f) => {
      novasFolgas[f.id] = [];
    });

    diasFuncionamento.forEach((dia) => {
      funcionarios.forEach((f) => {
        const select = document.querySelector(
          `.celula-escala[data-semana="${idxSemana}"][data-funcionario-id="${f.id}"][data-dia="${dia}"]`
        );
        const valor = select ? select.value : "folga";
        if (valor === "folga") {
          novasFolgas[f.id].push(dia);
        } else {
          novosTurnos[dia][valor].push(f.id);
        }
      });
    });

    for (let dia = 0; dia < 7; dia++) {
      if (!diasFuncionamento.includes(dia)) {
        funcionarios.forEach((f) => novasFolgas[f.id].push(dia));
      }
    }

    semana.folgas = novasFolgas;
    semana.turnos = novosTurnos;
  });
}

function renderAvisosGeracao(avisos) {
  const container = document.getElementById("avisos-geracao");
  if (!avisos || !avisos.length) {
    container.innerHTML = "";
    return;
  }
  const itens = avisos.map((a) => `<li>${escapeHtml(a)}</li>`).join("");
  container.innerHTML = `
    <div class="mensagem erro">
      <strong>Observações da geração automática:</strong>
      <ul style="margin: 6px 0 0; padding-left: 18px;">${itens}</ul>
    </div>
  `;
}

function aplicarDestaquesViolacoes(violacoes) {
  document.querySelectorAll(".celula-violacao").forEach((el) => el.classList.remove("celula-violacao"));
  if (!violacoes) return;

  violacoes.forEach((v) => {
    const semanaIdx = v.semana - 1;
    const tabela = document.querySelector(`#container-escala table[data-semana="${semanaIdx}"]`);
    if (!tabela) return;

    if (v.funcionario_id && v.dia !== null && v.dia !== undefined) {
      const select = tabela.querySelector(
        `.celula-escala[data-funcionario-id="${v.funcionario_id}"][data-dia="${v.dia}"]`
      );
      if (select) select.classList.add("celula-violacao");
    } else if (v.funcionario_id) {
      const nome = tabela.querySelector(`.celula-nome[data-funcionario-id="${v.funcionario_id}"]`);
      if (nome) nome.classList.add("celula-violacao");
    } else if (v.dia !== null && v.dia !== undefined) {
      const cabecalho = tabela.querySelector(`th[data-dia="${v.dia}"]`);
      if (cabecalho) cabecalho.classList.add("celula-violacao");
      if (v.turno_id) {
        tabela.querySelectorAll(`.celula-escala[data-dia="${v.dia}"]`).forEach((select) => {
          if (select.value === v.turno_id) select.classList.add("celula-violacao");
        });
      }
    }
  });
}

function renderViolacoes(violacoes) {
  aplicarDestaquesViolacoes(violacoes);
  const lista = document.getElementById("lista-violacoes");
  lista.innerHTML = "";
  if (!violacoes.length) {
    lista.innerHTML =
      '<li style="background:#e7f5ec;color:#1e6b3a;">Nenhuma violação encontrada. Escala conforme as regras configuradas.</li>';
    return;
  }
  violacoes.forEach((v) => {
    const li = document.createElement("li");
    li.className = v.nivel === "erro" ? "erro" : "alerta";
    const quem = v.funcionario_nome ? `${escapeHtml(v.funcionario_nome)} — ` : "";
    li.innerHTML = `${quem}${escapeHtml(v.mensagem)}<span class="base-legal">${escapeHtml(
      v.base_legal
    )}</span>`;
    lista.appendChild(li);
  });
}

function aplicarEstadoInicial(estado) {
  if (estado.empresa) {
    document.getElementById("nome-empresa").value = estado.empresa.nome || "";
    document.getElementById("setor-empresa").value = estado.empresa.setor;
    document.getElementById("fase-lei").value = estado.empresa.fase_lei;
    document.getElementById("carga-horaria").value = estado.empresa.carga_horaria_semanal;
    document.querySelectorAll(".chk-dia").forEach((chk) => {
      chk.checked = estado.empresa.dias_funcionamento.includes(parseInt(chk.value, 10));
    });
    turnos = (estado.empresa.turnos || []).map((t) => ({
      id: t.id,
      nome: t.nome,
      revezamento: !!t.revezamento,
    }));
    turnoContador = calcularProximoContador(turnos);
    renderTurnos();
    atualizarJornadaDiariaEstimada();
  }

  if (estado.funcionarios && estado.funcionarios.length) {
    funcionarios = estado.funcionarios.map((f) => ({
      id: f.id,
      nome: f.nome,
      sexo: f.sexo,
      turnosPermitidos: f.turnos_permitidos || [],
    }));
    funcionarioContador = calcularProximoContador(funcionarios);
    renderFuncionarios();
    atualizarResumoFuncionarios();
  }

  if (estado.escala) {
    ultimaEscala = estado.escala;
    renderAvisosGeracao(ultimaEscala.avisos || []);
    renderEscala(ultimaEscala);
    renderViolacoes(ultimaEscala.violacoes || []);
  }
}

function registrarEventos() {
  document.getElementById("carga-horaria").addEventListener("input", atualizarJornadaDiariaEstimada);

  document.getElementById("btn-add-turno").addEventListener("click", () => {
    const id = `t${turnoContador++}`;
    turnos.push({ id, nome: "", revezamento: false });
    // Por padrão, o novo turno já nasce marcado para todos os funcionários —
    // o usuário desmarca só quando algum funcionário não pode atuar nele.
    funcionarios.forEach((f) => {
      if (!f.turnosPermitidos.includes(id)) f.turnosPermitidos.push(id);
    });
    renderTurnos();
    renderFuncionarios();
  });

  document.getElementById("btn-limpar-formulario").addEventListener("click", () => {
    const vazio =
      !document.getElementById("nome-empresa").value &&
      !turnos.length;
    if (!vazio && !confirm("Limpar todos os dados da empresa e os turnos cadastrados nesta tela? Essa ação não pode ser desfeita.")) {
      return;
    }
    document.getElementById("form-empresa").reset();
    turnos = [];
    funcionarios.forEach((f) => {
      f.turnosPermitidos = [];
    });
    renderTurnos();
    renderFuncionarios();
    atualizarJornadaDiariaEstimada();
    document.getElementById("msg-empresa").innerHTML = "";
  });

  document.getElementById("lista-turnos").addEventListener("input", (e) => {
    const linha = e.target.closest(".linha-item");
    if (!linha) return;
    const turno = turnos.find((t) => t.id === linha.dataset.turnoId);
    if (!turno) return;
    if (e.target.classList.contains("turno-nome")) {
      turno.nome = e.target.value;
      renderFuncionarios();
    }
  });

  document.getElementById("lista-turnos").addEventListener("change", (e) => {
    const linha = e.target.closest(".linha-item");
    if (!linha) return;
    const turno = turnos.find((t) => t.id === linha.dataset.turnoId);
    if (!turno) return;
    if (e.target.classList.contains("turno-revezamento")) turno.revezamento = e.target.checked;
  });

  document.getElementById("lista-turnos").addEventListener("click", (e) => {
    if (!e.target.classList.contains("btn-remover-turno")) return;
    const linha = e.target.closest(".linha-item");
    const idRemovido = linha.dataset.turnoId;
    turnos = turnos.filter((t) => t.id !== idRemovido);
    funcionarios.forEach((f) => {
      f.turnosPermitidos = f.turnosPermitidos.filter((tid) => tid !== idRemovido);
    });
    renderTurnos();
    renderFuncionarios();
  });

  document.getElementById("btn-add-funcionario").addEventListener("click", () => {
    const id = `f${funcionarioContador++}`;
    // Por padrão, todos os turnos já nascem marcados — o usuário desmarca só
    // quando esse funcionário não pode atuar em algum turno específico.
    funcionarios.push({ id, nome: "", sexo: "M", turnosPermitidos: turnos.map((t) => t.id) });
    renderFuncionarios();
    atualizarResumoFuncionarios();
  });

  document.getElementById("lista-funcionarios").addEventListener("input", (e) => {
    const linha = e.target.closest(".linha-item");
    if (!linha) return;
    const f = funcionarios.find((x) => x.id === linha.dataset.funcionarioId);
    if (!f) return;
    if (e.target.classList.contains("funcionario-nome")) f.nome = e.target.value;
  });

  document.getElementById("lista-funcionarios").addEventListener("change", (e) => {
    const linha = e.target.closest(".linha-item");
    if (!linha) return;
    const f = funcionarios.find((x) => x.id === linha.dataset.funcionarioId);
    if (!f) return;
    if (e.target.classList.contains("funcionario-sexo")) {
      f.sexo = e.target.value;
      atualizarResumoFuncionarios();
    }
    if (e.target.classList.contains("chk-turno-funcionario")) {
      const turnoId = e.target.value;
      if (e.target.checked) {
        if (!f.turnosPermitidos.includes(turnoId)) f.turnosPermitidos.push(turnoId);
      } else {
        f.turnosPermitidos = f.turnosPermitidos.filter((id) => id !== turnoId);
      }
    }
  });

  document.getElementById("lista-funcionarios").addEventListener("click", (e) => {
    if (!e.target.classList.contains("btn-remover-funcionario")) return;
    const linha = e.target.closest(".linha-item");
    funcionarios = funcionarios.filter((f) => f.id !== linha.dataset.funcionarioId);
    renderFuncionarios();
    atualizarResumoFuncionarios();
  });

  document.getElementById("form-empresa").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("msg-empresa");
    try {
      const resultado = JSON.parse(ponte.salvar_empresa(JSON.stringify(montarEmpresaPayload())));
      if (resultado.ok) {
        msg.innerHTML = '<div class="mensagem sucesso">Dados da empresa salvos.</div>';
        await persistirBanco();
      } else {
        msg.innerHTML = `<div class="mensagem erro">${escapeHtml(resultado.erro)}</div>`;
      }
    } catch (erro) {
      console.error(erro);
      msg.innerHTML = `<div class="mensagem erro">Não foi possível salvar: ${escapeHtml(String(erro))}</div>`;
    }
  });

  document.getElementById("btn-salvar-funcionarios").addEventListener("click", async () => {
    const msg = document.getElementById("msg-funcionarios");
    try {
      ponte.salvar_funcionarios(JSON.stringify(montarFuncionariosPayload()));
      await persistirBanco();
      msg.innerHTML = '<div class="mensagem sucesso">Funcionários salvos.</div>';
    } catch (erro) {
      console.error(erro);
      msg.innerHTML = `<div class="mensagem erro">Não foi possível salvar: ${escapeHtml(String(erro))}</div>`;
    }
  });

  document.getElementById("btn-gerar-escala").addEventListener("click", async () => {
    const msg = document.getElementById("msg-escala");
    try {
      const resultadoEmpresa = JSON.parse(ponte.salvar_empresa(JSON.stringify(montarEmpresaPayload())));
      if (!resultadoEmpresa.ok) {
        msg.innerHTML = `<div class="mensagem erro">${escapeHtml(resultadoEmpresa.erro)}</div>`;
        return;
      }
      ponte.salvar_funcionarios(JSON.stringify(montarFuncionariosPayload()));

      const resultado = JSON.parse(ponte.gerar_escala());
      if (!resultado.ok) {
        msg.innerHTML = `<div class="mensagem erro">${escapeHtml(resultado.erro)}</div>`;
        return;
      }
      msg.innerHTML = "";
      ultimaEscala = resultado.escala;
      renderAvisosGeracao(ultimaEscala.avisos || []);
      renderEscala(ultimaEscala);
      renderViolacoes(ultimaEscala.violacoes || []);
      await persistirBanco();
    } catch (erro) {
      console.error(erro);
      msg.innerHTML = `<div class="mensagem erro">Não foi possível gerar a escala: ${escapeHtml(String(erro))}</div>`;
    }
  });

  document.getElementById("container-escala").addEventListener("change", async (e) => {
    if (!e.target.classList.contains("celula-escala") || !ultimaEscala) return;
    try {
      reconstruirEscalaDoDOM();
      const resultado = JSON.parse(ponte.validar_escala_editada(JSON.stringify(ultimaEscala)));
      if (resultado.ok) {
        ultimaEscala = resultado.escala;
        renderViolacoes(ultimaEscala.violacoes || []);
        await persistirBanco();
      }
    } catch (erro) {
      console.error(erro);
      document.getElementById("msg-escala").innerHTML =
        `<div class="mensagem erro">Não foi possível validar a alteração: ${escapeHtml(String(erro))}</div>`;
    }
  });

  document.getElementById("btn-exportar-csv").addEventListener("click", () => {
    if (!ultimaEscala) {
      alert("Gere a escala antes de exportar.");
      return;
    }
    // Mesma grade mostrada na tela/PDF (funcionário × dia, todas as semanas),
    // não só os dias trabalhados — para abrir igualzinho no Excel/planilha.
    const diasExibidos = diasExibidosNaEscala();
    const linhas = [["Semana", "Funcionário", ...diasExibidos.map((d) => NOMES_DIAS[d])].join(";")];
    ultimaEscala.semanas.forEach((semana, idxSemana) => {
      funcionarios.forEach((f) => {
        const linha = [`Semana ${idxSemana + 1}`, nomeExibicaoFuncionario(f)];
        diasExibidos.forEach((dia) => {
          const turnoId = turnoDoFuncionarioNoDia(semana, f.id, dia);
          const turnoEncontrado = turnos.find((t) => t.id === turnoId);
          linha.push(turnoId === "folga" ? "Folga" : turnoEncontrado ? nomeExibicaoTurno(turnoEncontrado) : turnoId);
        });
        linhas.push(linha.join(";"));
      });
    });
    baixarArquivo("escala.csv", linhas.join("\n"), "text/csv;charset=utf-8");
  });

  document.getElementById("btn-exportar-backup").addEventListener("click", () => {
    const json = ponte.exportar_backup();
    baixarArquivo("backup-escala.json", json, "application/json");
  });

  document.getElementById("btn-importar-backup").addEventListener("click", () => {
    document.getElementById("input-importar-backup").click();
  });

  document.getElementById("input-importar-backup").addEventListener("change", async (e) => {
    const arquivo = e.target.files[0];
    if (!arquivo) return;
    const texto = await arquivo.text();
    const estadoJson = ponte.importar_backup(texto);
    await persistirBanco();
    aplicarEstadoInicial(JSON.parse(estadoJson));
    document.getElementById("msg-escala").innerHTML =
      '<div class="mensagem sucesso">Backup importado.</div>';
  });

  document.getElementById("btn-imprimir").addEventListener("click", () => window.print());

  document.getElementById("btn-exportar-pdf").addEventListener("click", () => {
    if (!ultimaEscala) {
      alert("Gere a escala antes de exportar.");
      return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const nomeEmpresa = document.getElementById("nome-empresa").value || "Empresa";
    const diasExibidos = diasExibidosNaEscala();

    doc.setFontSize(14);
    doc.text(`Escala de trabalho — ${nomeEmpresa}`, 14, 16);
    doc.setFontSize(9);
    doc.text(`Gerado em ${new Date().toLocaleDateString("pt-BR")}`, 14, 22);

    let y = 30;
    ultimaEscala.semanas.forEach((semana, idx) => {
      const colunas = ["Funcionário", ...diasExibidos.map((d) => NOMES_DIAS[d])];
      const linhas = funcionarios.map((f) => {
        const linha = [nomeExibicaoFuncionario(f)];
        diasExibidos.forEach((dia) => {
          const turnoId = turnoDoFuncionarioNoDia(semana, f.id, dia);
          const turnoEncontrado = turnos.find((t) => t.id === turnoId);
          linha.push(turnoId === "folga" ? "Folga" : turnoEncontrado ? nomeExibicaoTurno(turnoEncontrado) : turnoId);
        });
        return linha;
      });
      doc.setFontSize(11);
      doc.text(`Semana ${idx + 1} de ${ultimaEscala.ciclo_semanas}`, 14, y);
      doc.autoTable({ head: [colunas], body: linhas, startY: y + 3, styles: { fontSize: 8 } });
      y = doc.lastAutoTable.finalY + 10;
      if (y > 260 && idx < ultimaEscala.semanas.length - 1) {
        doc.addPage();
        y = 20;
      }
    });

    const legenda = [
      "Regra geral: 1 domingo de folga a cada 7 semanas (Lei 605/1949).",
      "Comércio: 1 domingo de folga a cada 3 semanas (Lei 10.101/2000).",
      "Mulheres: independentemente do setor, pelo menos 1 domingo de folga a cada 15 dias (art. 386 da CLT).",
      "A EC 141/2026 recomenda que, dos 2 dias de descanso semanal, um seja preferencialmente o domingo.",
    ];
    if (y > 250) {
      doc.addPage();
      y = 20;
    }
    doc.setFontSize(8);
    legenda.forEach((linha) => {
      doc.text(`• ${linha}`, 14, y);
      y += 5;
    });

    const paginas = doc.internal.getNumberOfPages();
    for (let pagina = 1; pagina <= paginas; pagina++) {
      doc.setPage(pagina);
      doc.setFontSize(8);
      doc.text("CL Contabilidade", 14, 290);
    }

    doc.save("escala.pdf");
  });
}

async function iniciar() {
  registrarEventos();
  atualizarJornadaDiariaEstimada();

  pyodide = await loadPyodide();
  await pyodide.loadPackage("sqlite3");

  for (const nome of MODULOS_PYTHON) {
    const texto = await (await fetch(`python/${nome}.py`, { cache: "no-store" })).text();
    pyodide.FS.writeFile(`/${nome}.py`, texto);
  }

  const bytesSalvos = await idbGet("escala.db");
  if (bytesSalvos) {
    pyodide.FS.writeFile("/escala.db", new Uint8Array(bytesSalvos));
  }

  pyodide.runPython('import sys\nif "/" not in sys.path:\n    sys.path.insert(0, "/")');
  pyodide.runPython("import regras, gerador_escala, validador, persistencia, ponte");
  ponte = pyodide.globals.get("ponte");

  const estadoJson = ponte.inicializar();
  await persistirBanco();
  aplicarEstadoInicial(JSON.parse(estadoJson));

  document.getElementById("overlay-carregando").classList.add("oculto");
}

iniciar().catch((erro) => {
  console.error("Falha ao iniciar a aplicação:", erro);
  document.getElementById("overlay-carregando").innerHTML =
    '<div>Erro ao carregar a aplicação. Veja o console do navegador para detalhes.</div>';
});

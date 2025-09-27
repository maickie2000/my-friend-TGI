# GIT_WORKFLOW

Flujo simple para trabajar **dos personas** directamente en la rama **`main`** sin pisarse cambios.

## 0) Requisitos

* Tener **Git** instalado y configurado:

  ```bash
  git config --global user.name  "Tu Nombre"
  git config --global user.email "tu_correo@github"
  ```
* Clonar el repo y situarte en la carpeta del proyecto.

---

## 1) Reglas de oro (resumen en 1 línea)

**Antes de programar:**

```bash
git switch main && git pull origin main
```

**Después de programar:**

```bash
git add .
git commit -m "tipo: mensaje claro"
git pull origin main
git push origin main
```

> *Siempre haz `pull` antes de `push`.*

---

## 2) Mensajes de commit (convención corta)

Usa un **tipo** + descripción breve:

* `feat:` nueva funcionalidad
* `fix:` corrección de bug
* `chore:` mantenimiento (p. ej., `.gitignore`)
* `docs:` documentación
* `refactor:` cambio interno sin alterar comportamiento
* `perf:` mejora rendimiento
* `test:` tests

**Ejemplos**

```bash
git commit -m "feat: agrega test.py para validar parser XSECI"
git commit -m "fix: corrige regex de Q en flow2d_xseci"
git commit -m "chore: actualiza .gitignore para ignorar .venv"
```

---

## 3) Ignorar archivos no deseados

Asegúrate de tener este `.gitignore` (mínimo):

```
# entornos virtuales
.venv/
venv/
env/

# python cache
__pycache__/
*.pyc

# editors/IDE
.vscode/
.idea/
```

> Si por error agregaste `.venv` al staging:

```bash
git rm -r --cached .venv
git commit -m "chore: stop tracking .venv"
```

---

## 4) Flujo diario (detalle)

### 4.1. Traer últimos cambios (antes de empezar)

```bash
git switch main
git pull origin main
```

### 4.2. Trabajar y preparar cambios

```bash
# ...modificas archivos...
git add .
git commit -m "feat: describe tu cambio"
```

### 4.3. Integrar y publicar

```bash
git pull origin main   # integra posibles cambios remotos
git push origin main   # publica tus cambios
```

---

## 5) Resolver conflictos (si aparecen)

1. Tras `git pull origin main` Git te dirá qué archivos tienen conflictos.
2. Abre esos archivos, busca las marcas `<<<<<<<`, `=======`, `>>>>>>>` y **deja solo la versión correcta**.
3. Marca como resuelto y commitea:

   ```bash
   git add <archivo_conflictivo>
   git commit -m "fix: resuelve conflicto en <archivo>"
   git push origin main
   ```

---

## 6) Recuperación rápida

* **Deshacer cambios no añadidos (working dir):**

  ```bash
  git restore <archivo>
  ```
* **Sacar un archivo del staging (pero no borrarlo):**

  ```bash
  git restore --staged <archivo>
  ```
* **Ver historial de commits:**

  ```bash
  git log --oneline --graph --decorate --all
  ```
* **Ver qué cambió:**

  ```bash
  git status
  git diff          # antes de add
  git diff --staged # después de add
  ```

---

## 7) Checklist para cada push

* [ ] ¿Hice `git pull origin main` antes de empezar?
* [ ] ¿Commiteé con mensaje claro y tipo correcto?
* [ ] ¿Hice `git pull origin main` justo antes del `push`?
* [ ] ¿`.venv/` y `__pycache__/` están ignorados?

---

## 8) Roles y comunicación (sugerencia)

* Somos 2 en `main`. Avisarnos por chat:

  * “**Subí cambios al main**. Actualiza antes de trabajar.”
  * “**Voy a subir al main** en 5 min; avísame si estás subiendo algo.”

---

## 9) (Opcional) Ramas temporales

Si alguno necesita aislar un cambio grande, puede crear una rama y luego mezclarla a `main`:

```bash
git switch -c feat/nombre-corto
# ...trabajo...
git add . && git commit -m "feat: ..."
git switch main
git pull origin main
git merge feat/nombre-corto
git push origin main
```

---

## 10) Errores comunes

* **Se subió `.venv` por error**
  Ejecuta:

  ```bash
  git rm -r --cached .venv
  echo ".venv/" >> .gitignore
  git add .gitignore
  git commit -m "chore: ignore .venv"
  git push origin main
  ```

* **“Everything up-to-date” pero no veo mis cambios en GitHub**
  Te faltó `git add` o `git commit`. Revisa `git status`.

* **“Rejected” al hacer push**
  Alguien subió antes. Haz:

  ```bash
  git pull origin main
  # (resuelve conflictos si los hay)
  git push origin main
  ```

---

**Fin.**
Si algo no coincide con su forma de trabajo, editen este archivo y manténganlo como “regla de casa” dentro del repo.

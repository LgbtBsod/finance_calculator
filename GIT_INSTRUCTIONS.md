# Git инструкции для сборки и обновления

## Настройка Git репозитория

### Инициализация репозитория

```bash
# Инициализация нового репозитория
git init

# Добавление всех файлов
git add .

# Первый коммит
git commit -m "Initial commit: Modular architecture with kernel"

# Добавление удаленного репозитория
git remote add origin https://github.com/username/repo-name.git

# Push в удаленный репозиторий
git push -u origin main
```

### Ветвление

```bash
# Создание новой ветки для разработки
git checkout -b feature/new-feature

# Переключение между ветками
git checkout main
git checkout develop

# Слияние веток
git checkout main
git merge feature/new-feature

# Удаление ветки
git branch -d feature/new-feature
```

## Работа с тегами (версиями)

### Создание тегов

```bash
# Создание легкого тега
git tag v1.0.0

# Создание аннотированного тега (рекомендуется)
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push тега в удаленный репозиторий
git push origin v1.0.0

# Push всех тегов
git push origin --tags
```

### Семантическое версионирование

Формат: `MAJOR.MINOR.PATCH`

- **MAJOR**: Несовместимые изменения API
- **MINOR**: Новые функции, обратно совместимые
- **PATCH**: Исправления багов, обратно совместимые

Примеры:
- `1.0.0` - Первый релиз
- `1.0.1` - Исправление бага
- `1.1.0` - Новая функция
- `2.0.0` - Критические изменения

## CI/CD для автоматической сборки

### GitHub Actions (.github/workflows/build.yml)

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    
    runs-on: ${{ matrix.os }}
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pyinstaller
    
    - name: Get version from tag
      id: get_version
      run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT
    
    - name: Build executable
      run: |
        pyinstaller --onefile --name app core/main.py
    
    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: app-${{ matrix.os }}
        path: dist/app*
    
    - name: Create Release
      if: matrix.os == 'ubuntu-latest'
      uses: softprops/action-gh-release@v1
      with:
        files: |
          dist/app*
        body: |
          Release ${{ steps.get_version.outputs.VERSION }}
          
          ## Changes
          - Update DB Kernel with optimized queries
          - Add cache management module
          - Add auto-update functionality
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### GitLab CI (.gitlab-ci.yml)

```yaml
stages:
  - test
  - build
  - release

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.pip-cache"

cache:
  paths:
    - .pip-cache/

test:
  stage: test
  image: python:3.9
  script:
    - pip install -r requirements.txt
    - python -m pytest tests/

build-linux:
  stage: build
  image: python:3.9
  script:
    - pip install pyinstaller sqlalchemy
    - pyinstaller --onefile --name app core/main.py
  artifacts:
    paths:
      - dist/app

build-windows:
  stage: build
  tags:
    - windows
  script:
    - pip install pyinstaller sqlalchemy
    - pyinstaller --onefile --name app core/main.py
  artifacts:
    paths:
      - dist/app.exe

release:
  stage: release
  image: registry.gitlab.com/gitlab-org/release-cli:latest
  needs:
    - build-linux
    - build-windows
  script:
    - echo "Creating release for $CI_COMMIT_TAG"
  release:
    tag_name: $CI_COMMIT_TAG
    assets:
      links:
        - name: Linux Binary
          url: $CI_PROJECT_URL/-/jobs/artifacts/$CI_COMMIT_TAG/raw/dist/app?job=build-linux
        - name: Windows Binary
          url: $CI_PROJECT_URL/-/jobs/artifacts/$CI_COMMIT_TAG/raw/dist/app.exe?job=build-windows
```

## Хуки для автоматизации

### Pre-commit хук (.git/hooks/pre-commit)

```bash
#!/bin/bash

echo "Running pre-commit checks..."

# Запуск тестов
python -m pytest tests/ -q
if [ $? -ne 0 ]; then
    echo "Tests failed!"
    exit 1
fi

# Проверка стиля кода
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
if [ $? -ne 0 ]; then
    echo "Linting failed!"
    exit 1
fi

echo "Pre-commit checks passed!"
exit 0
```

### Post-merge хук для обновления версии

```bash
#!/bin/bash

# Автоматическое обновление VERSION файла после merge
VERSION=$(git describe --tags --always)
echo $VERSION > VERSION

echo "Version updated to $VERSION"
```

## Инструкция по обновлению через Git

### Для пользователей

```bash
# Клонирование репозитория
git clone https://github.com/username/repo-name.git
cd repo-name

# Получение обновлений
git pull origin main

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python core/main.py
```

### Для разработчиков

```bash
# Создание ветки для новой функции
git checkout -b feature/auto-update

# Внесение изменений и коммиты
git add .
git commit -m "feat: add auto-update module"

# Push ветки
git push origin feature/auto-update

# Создание Pull Request через GitHub/GitLab UI

# После мержа - получение обновлений
git checkout main
git pull origin main
```

## Откат к предыдущей версии

```bash
# Просмотр истории тегов
git tag -l

# Откат к конкретной версии
git checkout v1.0.0

# Или создание новой ветки из тега
git checkout -b hotfix-branch v1.0.0

# Принудительный откат (осторожно!)
git reset --hard v1.0.0
```

## Лучшие практики

1. **Частые коммиты** - делайте небольшие коммиты с понятными сообщениями
2. **Ветвление** - используйте feature branches для новых функций
3. **Теги** - тегируйте каждый релиз
4. **CI/CD** - автоматизируйте сборку и тестирование
5. **Code Review** - требуйте review перед мержем в main
6. **Semantic Versioning** - следуйте семантическому версионированию

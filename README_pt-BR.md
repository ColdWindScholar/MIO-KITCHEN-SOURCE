# MIO-KITCHEN-SOURCE #
![Banner](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)
#### Uma ferramenta ROM escrita em Python
> [!CAUTION]
> Proibido o uso comercial não autorizado
***
## Esta ferramenta usa muitos projetos de código aberto. Preste homenagem aos desenvolvedores!
***
## Localização
### 日本語: [ja-JP](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_ja-JP.md)
### 中文: [zh-CN](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_zh-CN.md)
### English: [en-US](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README.md)
### Deutsch: [de-DE](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_de-DE.md)
***
## Características
* Desempacote o `boot, dtbo, ext4, erofs, payload, logo` e assim por diante.
* Empacote o `boot, dtbo, ext4, erofs, payload, logo` e assim por diante.
***
## Vantagens
* Patch automático de fs_config e fs_context.
* Interface gráfica do usuário.
* Um gerenciador gráfico de plugins, além de um editor para edição de scripts de plugins. Suporte para instalação e exportação de plugins.
* Atualizações rápidas, seguras, estáveis ​​e rápidas.
* Intérprete o MSH exclusivo que suporta a execução de scripts MSH.
* Forneça compatibilidade com versões anteriores do Android 8 e inferior e crie .img para essas versões.
* Use o arquivo mkc e escolha a api no Linux, facilitando o uso.
***
## SO suportado

| SO      | Arquitetura            |
|---------|------------------------|
| Linux   | x86_64 arm64           |
| Windows | x86_64 x86 amd64 arm64 |
| Macos   | Arm64  X86             |

## * Aviso macOS
``` shell
# Se quiser usar [brotli], você precisa:
# Seu sistema já pode ter isso, então verifique primeiro
#
brew install gettext
```
## Comece a usar
> [!NOTE]
> Atualmente suporta apenas Python 3.8 e mais recente
### Pré-requisitos
<details><summary>macOS</summary>

```` shell
brew install python-tk python3  tcl-tk
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

<details><summary>Linux</summary>

```` shell
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
````

</details>

<details><summary>Windows</summary>

```` shell
python -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

### Iniciar
```` shell
python tool.py
# para criar uma distribuição binária, você poderia:
python build.py
````
***
# Contate-nos
***
### E-mail do desenvolvedor: 3590361911@qq.com
### Grupo QQ: 836898509
### Grupo do Telegram: [Mio Android Kitchen Chat](https://t.me/mio_android_kitchen_group)
### Canal do Telegram: [Mio Android Kitchen Updates](https://t.me/mio_android_kitchen)
***
# Contribuidores:
***
### Binário pré-construído do macOS para diversas ferramentas: [sk](https://github.com/sekaiacg)
### Alguma parte do código: [Affggh](https://github.com/affggh)
### Co-designer do logotipo: [Shaaim](https://github.com/786-shaaim)
### Tradutor japonês: [reindex-ot](https://github.com/reindex-ot)
### Tradutor português (Brasil): [igor](https://github.com/igormiguell)
### Tradutor alemão: [keldrion](https://github.com/keldrion)
### E MAIS...
### Obrigado a pessoas como você por ajudar!
***
# Sobre
***
### MIO-KITCHEN
```
Sempre gratuito aos primeiros usuários.
Ferramentas de qualidade estão aqui!
Escrito por MIO-KITCHEN-TEAM
```
#### ColdWindScholar (3590361911@qq.com) Todos os Direitos Reservados. ####

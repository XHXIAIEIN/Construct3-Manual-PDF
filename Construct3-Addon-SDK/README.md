# Construct 3 Addon SDK (PDF)

This repository contains PDF documentation extracted from the official Construct 3 Addon SDK manual.

## Source

All PDFs are downloaded and split from the official Construct 3 Addon SDK documentation:

> Source: `construct3-Addon-SDK.pdf` (152 pages, 62 sections)
> https://www.construct.net/en/make-games/manuals/addon-sdk

---

## Root Files

| File | Description |
|------|-------------|
| [home.pdf](home.pdf) | Addon SDK home page |
| [runtime-reference.pdf](runtime-reference.pdf) | Runtime API reference |

---

## Table of Contents

| Section | Files | Description |
|---------|:-----:|-------------|
| [Guide](#guide) | 21 | Development guide for creating addons |
| [Editor API Reference](#editor-api-reference) | 39 | Editor-side API interfaces |

---

## Guide

> 21 files

| File | Description |
|------|-------------|
| [c3addon-file.pdf](guide/c3addon-file.pdf) | The .c3addon file format |
| [addon-metadata.pdf](guide/addon-metadata.pdf) | Addon metadata configuration |
| [typescript-support.pdf](guide/typescript-support.pdf) | TypeScript support |
| [configuring-plugins.pdf](guide/configuring-plugins.pdf) | Configuring plugins |
| [configuring-behaviors.pdf](guide/configuring-behaviors.pdf) | Configuring behaviors |
| [configuring-effects.pdf](guide/configuring-effects.pdf) | Configuring effects |
| [defining-aces.pdf](guide/defining-aces.pdf) | Defining actions, conditions and expressions |
| [language-file.pdf](guide/language-file.pdf) | The language file |
| [editor-scripts.pdf](guide/editor-scripts.pdf) | Editor scripts |
| [runtime-scripts.pdf](guide/runtime-scripts.pdf) | Runtime scripts |
| [timeline-integration.pdf](guide/timeline-integration.pdf) | Timeline integration |
| [script-minification.pdf](guide/script-minification.pdf) | Script minification |
| [wrapper-extensions.pdf](guide/wrapper-extensions.pdf) | Wrapper extensions |
| [porting-c2-addons.pdf](guide/porting-c2-addons.pdf) | Porting Construct 2 plugins/behaviors |
| [porting-addon-sdk-v2.pdf](guide/porting-addon-sdk-v2.pdf) | Porting to Addon SDK v2 |
| [themes.pdf](guide/themes.pdf) | Theme addons |
| [enabling-developer-mode.pdf](guide/enabling-developer-mode.pdf) | Enabling Developer Mode |
| [using-developer-mode.pdf](guide/using-developer-mode.pdf) | Using Developer Mode |
| [safe-mode.pdf](guide/safe-mode.pdf) | Safe mode |

### Configuring Effects

| File | Description |
|------|-------------|
| [webgl-shaders.pdf](guide/configuring-effects/webgl-shaders.pdf) | WebGL shaders |
| [webgpu-shaders.pdf](guide/configuring-effects/webgpu-shaders.pdf) | WebGPU shaders |

---

## Editor API Reference

> 39 files

### Base Classes

| File | Description |
|------|-------------|
| [ibehaviorinstancebase.pdf](reference/base-classes/ibehaviorinstancebase.pdf) | IBehaviorInstanceBase interface |
| [iinstancebase.pdf](reference/base-classes/iinstancebase.pdf) | IInstanceBase interface |
| [iworldinstancebase.pdf](reference/base-classes/iworldinstancebase.pdf) | IWorldInstanceBase interface |

### Geometry Interfaces

| File | Description |
|------|-------------|
| [color.pdf](reference/geometry-interfaces/color.pdf) | Color interface |
| [quad.pdf](reference/geometry-interfaces/quad.pdf) | Quad interface |
| [rect.pdf](reference/geometry-interfaces/rect.pdf) | Rect interface |

### Graphics Interfaces

| File | Description |
|------|-------------|
| [idrawparams.pdf](reference/graphics-interfaces/idrawparams.pdf) | IDrawParams interface |
| [iwebglrenderer.pdf](reference/graphics-interfaces/iwebglrenderer.pdf) | IWebGLRenderer interface |
| [iwebgltext.pdf](reference/graphics-interfaces/iwebgltext.pdf) | IWebGLText interface |
| [iwebgltexture.pdf](reference/graphics-interfaces/iwebgltexture.pdf) | IWebGLTexture interface |

### Misc. Interfaces

| File | Description |
|------|-------------|
| [ilang.pdf](reference/misc-interfaces/ilang.pdf) | ILang interface |
| [izipfile.pdf](reference/misc-interfaces/izipfile.pdf) | IZipFile interface |
| [izipfileentry.pdf](reference/misc-interfaces/izipfileentry.pdf) | IZipFileEntry interface |

### Model Interfaces

| File | Description |
|------|-------------|
| [ieventblock.pdf](reference/model-interfaces/ieventblock.pdf) | IEventBlock interface |
| [ieventparentrow.pdf](reference/model-interfaces/ieventparentrow.pdf) | IEventParentRow interface |
| [ieventsheet.pdf](reference/model-interfaces/ieventsheet.pdf) | IEventSheet interface |
| [ilayer.pdf](reference/model-interfaces/ilayer.pdf) | ILayer interface |
| [ilayout.pdf](reference/model-interfaces/ilayout.pdf) | ILayout interface |
| [iproject.pdf](reference/model-interfaces/iproject.pdf) | IProject interface |
| [iprojectfile.pdf](reference/model-interfaces/iprojectfile.pdf) | IProjectFile interface |

### Object Interfaces

| File | Description |
|------|-------------|
| [ianimation.pdf](reference/object-interfaces/ianimation.pdf) | IAnimation interface |
| [ianimationframe.pdf](reference/object-interfaces/ianimationframe.pdf) | IAnimationFrame interface |
| [ibehaviorinstance.pdf](reference/object-interfaces/ibehaviorinstance.pdf) | IBehaviorInstance interface |
| [ibehaviortype.pdf](reference/object-interfaces/ibehaviortype.pdf) | IBehaviorType interface |
| [icollisionpoly.pdf](reference/object-interfaces/icollisionpoly.pdf) | ICollisionPoly interface |
| [icontainer.pdf](reference/object-interfaces/icontainer.pdf) | IContainer interface |
| [ifamily.pdf](reference/object-interfaces/ifamily.pdf) | IFamily interface |
| [iimagepoint.pdf](reference/object-interfaces/iimagepoint.pdf) | IImagePoint interface |
| [iobjectclass.pdf](reference/object-interfaces/iobjectclass.pdf) | IObjectClass interface |
| [iobjectinstance.pdf](reference/object-interfaces/iobjectinstance.pdf) | IObjectInstance interface |
| [iobjecttype.pdf](reference/object-interfaces/iobjecttype.pdf) | IObjectType interface |
| [iworldinstance.pdf](reference/object-interfaces/iworldinstance.pdf) | IWorldInstance interface |

### UI Interfaces

| File | Description |
|------|-------------|
| [ilayoutview.pdf](reference/ui-interfaces/ilayoutview.pdf) | ILayoutView interface |
| [utilities.pdf](reference/ui-interfaces/utilities.pdf) | Utilities interface |

### Other Reference

| File | Description |
|------|-------------|
| [finding-addon-ids.pdf](reference/finding-addon-ids.pdf) | Finding addon IDs |
| [ibehaviorinfo.pdf](reference/ibehaviorinfo.pdf) | IBehaviorInfo interface |
| [iplugininfo.pdf](reference/iplugininfo.pdf) | IPluginInfo interface |
| [pluginproperty.pdf](reference/pluginproperty.pdf) | PluginProperty class |
| [specifying-dependencies.pdf](reference/specifying-dependencies.pdf) | Specifying dependencies |

---

## License

All content belongs to Scirra Ltd. This repository is for personal learning and reference purposes only.

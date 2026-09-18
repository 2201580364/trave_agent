import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const assetVersion = process.env.H5_ASSET_VERSION
if (!assetVersion || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(assetVersion)) {
  throw new Error(
    'H5_ASSET_VERSION must contain 1-128 letters, digits, dots, underscores, or hyphens.'
  )
}

const dist = path.resolve(import.meta.dirname, '..', 'dist')
const appPath = path.join(dist, 'js', 'app.js')
const indexPath = path.join(dist, 'index.html')
const markerPath = path.join(dist, '.release-asset-version')
const versionQuery = `?v=${assetVersion}`

function replaceRequired(content, search, replacement, filePath) {
  if (!content.includes(search)) {
    throw new Error(`Expected H5 build token is absent from ${filePath}: ${search}`)
  }
  return content.replaceAll(search, replacement)
}

let app = await readFile(appPath, 'utf8')
app = replaceRequired(app, 'return"chunk/"+a+".js"', `return"chunk/"+a+".js${versionQuery}"`, appPath)
app = replaceRequired(app, 'return"css/"+a+".css"', `return"css/"+a+".css${versionQuery}"`, appPath)
await writeFile(appPath, app, 'utf8')

let index = await readFile(indexPath, 'utf8')
index = replaceRequired(index, '/js/232.js', `/js/232.js${versionQuery}`, indexPath)
index = replaceRequired(index, '/js/app.js', `/js/app.js${versionQuery}`, indexPath)
index = replaceRequired(index, '/css/app.css', `/css/app.css${versionQuery}`, indexPath)
await writeFile(indexPath, index, 'utf8')
await writeFile(markerPath, `${assetVersion}\n`, 'utf8')

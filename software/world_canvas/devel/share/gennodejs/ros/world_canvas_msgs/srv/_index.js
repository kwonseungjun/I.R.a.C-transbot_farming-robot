
"use strict";

let GetAnnotationsData = require('./GetAnnotationsData.js')
let DeleteAnnotations = require('./DeleteAnnotations.js')
let ListWorlds = require('./ListWorlds.js')
let PubAnnotationsData = require('./PubAnnotationsData.js')
let YAMLImport = require('./YAMLImport.js')
let DeleteMap = require('./DeleteMap.js')
let SaveAnnotationsData = require('./SaveAnnotationsData.js')
let ListMaps = require('./ListMaps.js')
let SetKeyword = require('./SetKeyword.js')
let ResetDatabase = require('./ResetDatabase.js')
let SaveMap = require('./SaveMap.js')
let YAMLExport = require('./YAMLExport.js')
let GetAnnotations = require('./GetAnnotations.js')
let PublishMap = require('./PublishMap.js')
let SetRelationship = require('./SetRelationship.js')
let RenameMap = require('./RenameMap.js')
let EditAnnotationsData = require('./EditAnnotationsData.js')

module.exports = {
  GetAnnotationsData: GetAnnotationsData,
  DeleteAnnotations: DeleteAnnotations,
  ListWorlds: ListWorlds,
  PubAnnotationsData: PubAnnotationsData,
  YAMLImport: YAMLImport,
  DeleteMap: DeleteMap,
  SaveAnnotationsData: SaveAnnotationsData,
  ListMaps: ListMaps,
  SetKeyword: SetKeyword,
  ResetDatabase: ResetDatabase,
  SaveMap: SaveMap,
  YAMLExport: YAMLExport,
  GetAnnotations: GetAnnotations,
  PublishMap: PublishMap,
  SetRelationship: SetRelationship,
  RenameMap: RenameMap,
  EditAnnotationsData: EditAnnotationsData,
};

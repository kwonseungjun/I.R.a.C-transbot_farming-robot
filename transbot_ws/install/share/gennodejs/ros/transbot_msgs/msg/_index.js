
"use strict";

let Arm = require('./Arm.js');
let Edition = require('./Edition.js');
let Joint = require('./Joint.js');
let Battery = require('./Battery.js');
let LaserAvoid = require('./LaserAvoid.js');
let Image_Msg = require('./Image_Msg.js');
let PWMServo = require('./PWMServo.js');
let PatrolWarning = require('./PatrolWarning.js');
let SensorState = require('./SensorState.js');
let PointArray = require('./PointArray.js');
let Adjust = require('./Adjust.js');
let JoyState = require('./JoyState.js');
let Position = require('./Position.js');
let General = require('./General.js');

module.exports = {
  Arm: Arm,
  Edition: Edition,
  Joint: Joint,
  Battery: Battery,
  LaserAvoid: LaserAvoid,
  Image_Msg: Image_Msg,
  PWMServo: PWMServo,
  PatrolWarning: PatrolWarning,
  SensorState: SensorState,
  PointArray: PointArray,
  Adjust: Adjust,
  JoyState: JoyState,
  Position: Position,
  General: General,
};

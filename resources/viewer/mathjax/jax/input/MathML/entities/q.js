/*************************************************************
 *
 *  MathJax/jax/output/HTML-CSS/entities/q.js
 *
 *  Copyright (c) 2010 Design Science, Inc.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 */

(function (MATHML) {
  MathJax.Hub.Insert(MATHML.Parse.Entity,{
    'QUOT': '\u0022',
    'qint': '\u2A0C',
    'qprime': '\u2057',
    'quaternions': '\u210D',
    'quatint': '\u2A16',
    'quest': '\u003F',
    'questeq': '\u225F',
    'quot': '\u0022'
  });

  MathJax.Ajax.loadComplete(MATHML.entityDir+"/q.js");

})(MathJax.InputJax.MathML);

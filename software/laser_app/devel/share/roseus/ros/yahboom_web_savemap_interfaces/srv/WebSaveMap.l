;; Auto-generated. Do not edit!


(when (boundp 'yahboom_web_savemap_interfaces::WebSaveMap)
  (if (not (find-package "YAHBOOM_WEB_SAVEMAP_INTERFACES"))
    (make-package "YAHBOOM_WEB_SAVEMAP_INTERFACES"))
  (shadow 'WebSaveMap (find-package "YAHBOOM_WEB_SAVEMAP_INTERFACES")))
(unless (find-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAP")
  (make-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAP"))
(unless (find-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAPREQUEST")
  (make-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAPREQUEST"))
(unless (find-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAPRESPONSE")
  (make-package "YAHBOOM_WEB_SAVEMAP_INTERFACES::WEBSAVEMAPRESPONSE"))

(in-package "ROS")





(defclass yahboom_web_savemap_interfaces::WebSaveMapRequest
  :super ros::object
  :slots (_mapname ))

(defmethod yahboom_web_savemap_interfaces::WebSaveMapRequest
  (:init
   (&key
    ((:mapname __mapname) "")
    )
   (send-super :init)
   (setq _mapname (string __mapname))
   self)
  (:mapname
   (&optional __mapname)
   (if __mapname (setq _mapname __mapname)) _mapname)
  (:serialization-length
   ()
   (+
    ;; string _mapname
    4 (length _mapname)
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; string _mapname
       (write-long (length _mapname) s) (princ _mapname s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; string _mapname
     (let (n) (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4) (setq _mapname (subseq buf ptr- (+ ptr- n))) (incf ptr- n))
   ;;
   self)
  )

(defclass yahboom_web_savemap_interfaces::WebSaveMapResponse
  :super ros::object
  :slots (_response ))

(defmethod yahboom_web_savemap_interfaces::WebSaveMapResponse
  (:init
   (&key
    ((:response __response) "")
    )
   (send-super :init)
   (setq _response (string __response))
   self)
  (:response
   (&optional __response)
   (if __response (setq _response __response)) _response)
  (:serialization-length
   ()
   (+
    ;; string _response
    4 (length _response)
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; string _response
       (write-long (length _response) s) (princ _response s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; string _response
     (let (n) (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4) (setq _response (subseq buf ptr- (+ ptr- n))) (incf ptr- n))
   ;;
   self)
  )

(defclass yahboom_web_savemap_interfaces::WebSaveMap
  :super ros::object
  :slots ())

(setf (get yahboom_web_savemap_interfaces::WebSaveMap :md5sum-) "f49bd6f76bfef516e6ae3dd7ae161f79")
(setf (get yahboom_web_savemap_interfaces::WebSaveMap :datatype-) "yahboom_web_savemap_interfaces/WebSaveMap")
(setf (get yahboom_web_savemap_interfaces::WebSaveMap :request) yahboom_web_savemap_interfaces::WebSaveMapRequest)
(setf (get yahboom_web_savemap_interfaces::WebSaveMap :response) yahboom_web_savemap_interfaces::WebSaveMapResponse)

(defmethod yahboom_web_savemap_interfaces::WebSaveMapRequest
  (:response () (instance yahboom_web_savemap_interfaces::WebSaveMapResponse :init)))

(setf (get yahboom_web_savemap_interfaces::WebSaveMapRequest :md5sum-) "f49bd6f76bfef516e6ae3dd7ae161f79")
(setf (get yahboom_web_savemap_interfaces::WebSaveMapRequest :datatype-) "yahboom_web_savemap_interfaces/WebSaveMapRequest")
(setf (get yahboom_web_savemap_interfaces::WebSaveMapRequest :definition-)
      "string mapname
---
string response

")

(setf (get yahboom_web_savemap_interfaces::WebSaveMapResponse :md5sum-) "f49bd6f76bfef516e6ae3dd7ae161f79")
(setf (get yahboom_web_savemap_interfaces::WebSaveMapResponse :datatype-) "yahboom_web_savemap_interfaces/WebSaveMapResponse")
(setf (get yahboom_web_savemap_interfaces::WebSaveMapResponse :definition-)
      "string mapname
---
string response

")



(provide :yahboom_web_savemap_interfaces/WebSaveMap "f49bd6f76bfef516e6ae3dd7ae161f79")



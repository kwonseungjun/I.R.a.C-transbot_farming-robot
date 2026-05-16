; Auto-generated. Do not edit!


(cl:in-package yahboom_web_savemap_interfaces-srv)


;//! \htmlinclude WebSaveMap-request.msg.html

(cl:defclass <WebSaveMap-request> (roslisp-msg-protocol:ros-message)
  ((mapname
    :reader mapname
    :initarg :mapname
    :type cl:string
    :initform ""))
)

(cl:defclass WebSaveMap-request (<WebSaveMap-request>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <WebSaveMap-request>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'WebSaveMap-request)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name yahboom_web_savemap_interfaces-srv:<WebSaveMap-request> is deprecated: use yahboom_web_savemap_interfaces-srv:WebSaveMap-request instead.")))

(cl:ensure-generic-function 'mapname-val :lambda-list '(m))
(cl:defmethod mapname-val ((m <WebSaveMap-request>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader yahboom_web_savemap_interfaces-srv:mapname-val is deprecated.  Use yahboom_web_savemap_interfaces-srv:mapname instead.")
  (mapname m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <WebSaveMap-request>) ostream)
  "Serializes a message object of type '<WebSaveMap-request>"
  (cl:let ((__ros_str_len (cl:length (cl:slot-value msg 'mapname))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_str_len) ostream))
  (cl:map cl:nil #'(cl:lambda (c) (cl:write-byte (cl:char-code c) ostream)) (cl:slot-value msg 'mapname))
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <WebSaveMap-request>) istream)
  "Deserializes a message object of type '<WebSaveMap-request>"
    (cl:let ((__ros_str_len 0))
      (cl:setf (cl:ldb (cl:byte 8 0) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'mapname) (cl:make-string __ros_str_len))
      (cl:dotimes (__ros_str_idx __ros_str_len msg)
        (cl:setf (cl:char (cl:slot-value msg 'mapname) __ros_str_idx) (cl:code-char (cl:read-byte istream)))))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<WebSaveMap-request>)))
  "Returns string type for a service object of type '<WebSaveMap-request>"
  "yahboom_web_savemap_interfaces/WebSaveMapRequest")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'WebSaveMap-request)))
  "Returns string type for a service object of type 'WebSaveMap-request"
  "yahboom_web_savemap_interfaces/WebSaveMapRequest")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<WebSaveMap-request>)))
  "Returns md5sum for a message object of type '<WebSaveMap-request>"
  "f49bd6f76bfef516e6ae3dd7ae161f79")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'WebSaveMap-request)))
  "Returns md5sum for a message object of type 'WebSaveMap-request"
  "f49bd6f76bfef516e6ae3dd7ae161f79")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<WebSaveMap-request>)))
  "Returns full string definition for message of type '<WebSaveMap-request>"
  (cl:format cl:nil "string mapname~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'WebSaveMap-request)))
  "Returns full string definition for message of type 'WebSaveMap-request"
  (cl:format cl:nil "string mapname~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <WebSaveMap-request>))
  (cl:+ 0
     4 (cl:length (cl:slot-value msg 'mapname))
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <WebSaveMap-request>))
  "Converts a ROS message object to a list"
  (cl:list 'WebSaveMap-request
    (cl:cons ':mapname (mapname msg))
))
;//! \htmlinclude WebSaveMap-response.msg.html

(cl:defclass <WebSaveMap-response> (roslisp-msg-protocol:ros-message)
  ((response
    :reader response
    :initarg :response
    :type cl:string
    :initform ""))
)

(cl:defclass WebSaveMap-response (<WebSaveMap-response>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <WebSaveMap-response>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'WebSaveMap-response)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name yahboom_web_savemap_interfaces-srv:<WebSaveMap-response> is deprecated: use yahboom_web_savemap_interfaces-srv:WebSaveMap-response instead.")))

(cl:ensure-generic-function 'response-val :lambda-list '(m))
(cl:defmethod response-val ((m <WebSaveMap-response>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader yahboom_web_savemap_interfaces-srv:response-val is deprecated.  Use yahboom_web_savemap_interfaces-srv:response instead.")
  (response m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <WebSaveMap-response>) ostream)
  "Serializes a message object of type '<WebSaveMap-response>"
  (cl:let ((__ros_str_len (cl:length (cl:slot-value msg 'response))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_str_len) ostream))
  (cl:map cl:nil #'(cl:lambda (c) (cl:write-byte (cl:char-code c) ostream)) (cl:slot-value msg 'response))
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <WebSaveMap-response>) istream)
  "Deserializes a message object of type '<WebSaveMap-response>"
    (cl:let ((__ros_str_len 0))
      (cl:setf (cl:ldb (cl:byte 8 0) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'response) (cl:make-string __ros_str_len))
      (cl:dotimes (__ros_str_idx __ros_str_len msg)
        (cl:setf (cl:char (cl:slot-value msg 'response) __ros_str_idx) (cl:code-char (cl:read-byte istream)))))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<WebSaveMap-response>)))
  "Returns string type for a service object of type '<WebSaveMap-response>"
  "yahboom_web_savemap_interfaces/WebSaveMapResponse")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'WebSaveMap-response)))
  "Returns string type for a service object of type 'WebSaveMap-response"
  "yahboom_web_savemap_interfaces/WebSaveMapResponse")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<WebSaveMap-response>)))
  "Returns md5sum for a message object of type '<WebSaveMap-response>"
  "f49bd6f76bfef516e6ae3dd7ae161f79")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'WebSaveMap-response)))
  "Returns md5sum for a message object of type 'WebSaveMap-response"
  "f49bd6f76bfef516e6ae3dd7ae161f79")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<WebSaveMap-response>)))
  "Returns full string definition for message of type '<WebSaveMap-response>"
  (cl:format cl:nil "string response~%~%~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'WebSaveMap-response)))
  "Returns full string definition for message of type 'WebSaveMap-response"
  (cl:format cl:nil "string response~%~%~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <WebSaveMap-response>))
  (cl:+ 0
     4 (cl:length (cl:slot-value msg 'response))
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <WebSaveMap-response>))
  "Converts a ROS message object to a list"
  (cl:list 'WebSaveMap-response
    (cl:cons ':response (response msg))
))
(cl:defmethod roslisp-msg-protocol:service-request-type ((msg (cl:eql 'WebSaveMap)))
  'WebSaveMap-request)
(cl:defmethod roslisp-msg-protocol:service-response-type ((msg (cl:eql 'WebSaveMap)))
  'WebSaveMap-response)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'WebSaveMap)))
  "Returns string type for a service object of type '<WebSaveMap>"
  "yahboom_web_savemap_interfaces/WebSaveMap")
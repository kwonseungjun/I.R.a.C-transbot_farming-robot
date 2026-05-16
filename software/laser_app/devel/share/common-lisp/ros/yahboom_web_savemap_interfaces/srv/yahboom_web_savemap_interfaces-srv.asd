
(cl:in-package :asdf)

(defsystem "yahboom_web_savemap_interfaces-srv"
  :depends-on (:roslisp-msg-protocol :roslisp-utils )
  :components ((:file "_package")
    (:file "WebSaveMap" :depends-on ("_package_WebSaveMap"))
    (:file "_package_WebSaveMap" :depends-on ("_package"))
  ))
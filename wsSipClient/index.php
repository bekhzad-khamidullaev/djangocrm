<?php

//Окно списка заказов
if (!$user->allow('menu','dispatcher')) halt ('Доступ закрыт!');

$template = [
	'title' => 'Пульт',
	// 'icon' => 'ico/nav/car.png',
	'mainmenu' => 'slide',
	'includeToEnd' => '/dispatcher/_settings.php',
	'js' => [
		'//www.google.com/jsapi',
		'//api-maps.yandex.ru/2.1/?lang=ru-RU',
		'site/orders/orders1.js',
		'site/orders/orders2.js',
		'map.js',
		'SIPml-api.js?svn=230',
		'SIPml-phone.js?svn=230',
	],
];
$access = isset($user->access['dispatcher']) ? $user->access['dispatcher'] : [];
include _FILE_(MODULES_PATH . "header.php");
?>
		<input id="disable-close" type="hidden" value="true" />
	<?php if(!($access['disableDriver'] || $access['disableSos'] || $access['disableTraffic'])){?>
		<div id="container-left" class="container-nav container-nav-xsmall">
			<div class="container-wrap">
				<div class="container">
					<div class="vspan0">
						<div class="container-wrap">
							<div class="container">
							<?php if(!$access['disableDriver']){?>
								<div class="container-nav-panel vertical-stacked-small disableDriver">
									<div class="select-default input-block-level">
										<select id="drivers-filter" class="input-block-level">
											<option value="1">Водители на смене</option>
											<option value="0">Свободные</option>
											<option value="2">Все</option>
										</select>
										<div class="caret"></div>
									</div>
									<input class="input-block-level input-text input-search" type="text" id="drivers-search" placeholder="Поиск" />
								</div>
								<div class="vspan7 container-white disableDriver">
									<div id="table-drivers" class="datagrid datagrid-striped datagrid-selected datagrid-vertical-top datagrid-disable-scroll-h no-loader" data-open="driver" data-header="false"></div>
								</div>
							<?php }?>
							<?php if(!$access['disableSos']){?>
								<div id="panel-sos" class="vspan3 sos disableSos">
									<div class="title"><b>Сообщения</b></div>
									<div class="sos-container">
										<div id="table-sos" class="datagrid datagrid-nohover datagrid-transparent datagrid-striped datagrid-striped-noborder datagrid-auto-scroll datagrid-disable-scroll-h size11 no-loader" data-header="false"></div>	
									</div>
								</div>
							<?php }?>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	<?php }?>
		<div id="container-content" class="hspan0">
			<div class="container-wrap">
				<div class="container">
					<?php
			include _FILE_($config['activeDir'].'/_topmenu.php')?>
					<div class="vspan0 container-form">
						<input id="voip" name="voip" type="hidden" value="True" />
						<div class="container-wrap">
							<div class="container">
								<ul class="toolbar-filter">
									<li class="filter-view-status">
									<?php if ($access['filterView']<0 || !isset($access['filterView'])){?>
										<div class="select-default">
											<select class="select-default filter-change" id="filter-view" name="filter-view" style="width: 110px;">
												<?=getConstOptions('orderFilter',$access['filterView'])?>
											</select>
											<div class="caret"></div>
										</div>
									<?php }else{?>
										<input id="filter-view" name="filter-view" type="hidden" value="<?=$access['filterView']?>" />
										<span><?=$consts['orderFilter'][$access['filterView']]?></span>
									<?php }?>
									</li>
									<li class="divider filter-view-status"></li>
									<li class="filter-period filter-period-visible hide">
										<div class="select-default">
											<select id="filter-period" class="filter-change">
												<option value="0" selected="selected">Дата:</option>
												<option value="1">Период:</option>
											</select>
											<div class="caret"></div>
										</div>
									</li>
									<li class="filter-period filter-period-0 hide">
										<input id="filter-date" class="filter-change" type="date" required="required" value="<?=date("Y-m-d")?>" />
									</li>
									<li class="filter-period filter-period-1 hide">
										<input id="filter-date1" class="filter-change" type="datetime-local" required="required" value="<?=formatDT(true,mktime(10,0,0))?>" />
										<span>–</span>
										<input id="filter-date2" class="filter-change" type="datetime-local" required="required" value="<?=formatDT(true,mktime(10,0,0,date('m'),date('d')+1))?>" />
									</li>
									<li class="divider filter-period filter-period-visible hide"></li>
									<li class="filter-view-search">
										<div class="select-default">
											<select id="filter-search-query">
												<option value="0" selected="selected">№ заказа</option>
												<option value="1" >Позывной</option>
												<option value="2" >Откуда</option>
												<option value="3" >Куда</option>
												<option value="4" >Телефон</option>
												<option value="5" >Сумма</option>
												<option value="6" >Компания</option>
												<option value="7" >ID</option>
											</select>
											<div class="caret"></div>
										</div>
									</li>
									<li class="filter-view-search"><input id="filter-search" type="text" placeholder="поиск" /></li>
									<li class="filter-view-search"><button id="btn-search" class="btn btn-default">Найти</button></li>
									<li class="divider filter-view-type"></li>
									<li class="filter-view-type">
										<div class="select-default">
											<select id="filter-types" class="filter-change" data-empty="true" data-empty-text="(тип заказа)" data-group="false" data-source="/api/selector/rulesorder"></select>
											<div class="caret"></div>
										</div>
									</li>
									<li class="divider filter-view-type"></li>
									<li class="filter-view-type">
										<div class="select-default">
											<select id="filter-category" class="filter-change">
												<option value='0'>(категория)</option>
												<?=getConstOptions('carCategory',0)?>
											</select>
											<div class="caret"></div>
										</div>
									</li>
								</ul>
								<ul class="toolbar">
									<li>
										<div id="buttons-show" class="btn-group" data-toggle="buttons-radio">
											<button value="table" rel="tooltip" data-original-title="Табличный вид" class="btn btn-default btn-icon active"><img src="/assets/ico/nav/list.png"></button>
											<?php if(!$access['disableGraph']&&false){?><button value="schedule" rel="tooltip" data-original-title="График загруженности" class="btn btn-default btn-icon disableGraph"><i class="icon-th"></i></button><?php }?>
											<?php if(!$access['disableMap']){?><button value="map" rel="tooltip" data-original-title="Карта" class="btn btn-default btn-icon disableMap"><img src="/assets/ico/nav/world.png"></button><?php }?>
											<?php if(!$access['disableStat']){?><button value="chart" rel="tooltip" data-original-title="Статистика" class="btn btn-default btn-icon disableStat"><img src="/assets/ico/nav/statistics.png"></button><?php }?>
										</div>
									</li>
									<li class="divider"></li>
									<li><button rel="tooltip" data-original-title="Обновить" id="btn-update" class="btn btn-default btn-icon"><img src="/assets/ico/nav/refresh2.png" /></button></li>
								<?php if(!$access['disableConfig']){?>
									<li><button id="btn-settings" rel="tooltip" data-original-title="Настройки" class="dropdown-toggle btn btn-default btn-icon disableConfig" data-target="#modal-sos-settings" data-toggle="modal"><img src="/assets/ico/nav/settings.png"></button></li>
								<?php }?>
									<li class="divider"></li>
								<?php if(!$access['disableNew']){?>
									<li>
										<div class="btn-group disableNew">
											<button id="btn-new" class="btn btn-default btn-icon-text">
												<span><img src="/assets/ico/nav/plus2.png" alt="" />&nbsp;Новый<span class="hidden-tablet">&nbsp;(F2)</span></span>
											</button>
										</div>
									</li>
									<li class="divider"></li>
								<?php }?>
									<li><button id="btn-status-3" rel="btn-status" data-status="3" class="btn btn-default" disabled="disabled">На месте<span class="hidden-tablet"> (F6)</span></button></li>
									<li><button id="btn-status-4" rel="btn-status" data-status="4" class="btn btn-default" disabled="disabled">Отзвонились<span class="hidden-tablet"> (F7)</span></button></li>
									<li><button id="btn-status-5" rel="btn-status" data-status="5" class="btn btn-default" disabled="disabled">В пути<span class="hidden-tablet"> (F8)</span></button></li>
									<li class="divider"></li>
								</ul>
								<div id="show-table" class="vspan0 hide">
									<div class="container-wrap">
										<div class="container">
											<div class="vspan6">
												<div id="table1" class="datagrid datagrid-single datagrid-selected no-loader" data-open="order">
												</div>
											</div>
											<div class="statusbar statusbar-large hidden-phone"><b>В пути</b></div>
											<div class="vspan4 hidden-phone">
												<div id="table2" class="datagrid datagrid-single datagrid-selected no-loader" data-open="order">
												</div>
											</div>
										</div>
									</div>
								</div>
							<?php if(!$access['disableGraph']&&false){?>
								<div id="show-schedule" class="vspan0 hide">
									<div class="container-wrap">
										<div class="container">
											<div class="vspan5 border-bottom">
												<div id="table3" class="datagrid datagrid-schedule datagrid-single datagrid-selected datagrid-header-center no-loader" data-open="order"></div>
												<div class="zoom-control hidden-mobile">
													<input id="table3-zoom" type="text" class="slider" value="" data-slider-min="40"
														data-slider-max="120" data-slider-step="10" data-slider-value="100" data-slider-orientation="vertical"
														data-slider-selection="after" data-slider-tooltip="hide">
												</div>
											</div>
											<div class="vspan5">
												<input id="map-city-lat" type="hidden" value="41.551761" />
												<input id="map-city-lon" type="hidden" value="60.631444" />
												<input id="map-city-zoom" type="hidden" value="14" />
												<div class="container-fill" id="map-schedule" data-orders="false" data-drivers="true">
													<div class="ymaps-trafic hide">
														<div class="content">
															<b id="map-route-distance"></b>&nbsp;или&nbsp;<b id="map-route-time"></b>&nbsp;с учётом пробок<br>
															<span class="green">Стоимость:&nbsp;<b id="map-route-cost"></b>&nbsp;руб</span>
														</div>
													</div>
													<div class="ym-panel-cars ym-panel hide">
														<div class="content split">
															<div>ТС: <span id="CarsAll" style="font-weight: bold;">0</span></div>
															<div>Заказов: <span id="OrdersAll" style="font-weight: bold;">0</span></div>
														</div>	  
														<div class="content">
															<div class="row">
																<div class="span1">[<span id="CarsInviteP">0</span>%]</div>
																<div class="span2">Свободно</div>
																<div class="span3"><span id="CarsInvite" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsOrdersP">0</span>%]</div>
																<div class="span2">На заказе</div>
																<div class="span3"><span id="CarsOrders" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsBusyP">0</span>%]</div>
																<div class="span2">Занято</div>
																<div class="span3"><span id="CarsBusy" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsNoGpsP">0</span>%]</div>
																<div class="span2">Нет GPS</div>
																<div class="span3"><span id="CarsNoGps" style="font-weight: bold;">0</span></div>
															</div>		
														</div>  
													</div>
												</div>
											</div>
										</div>
									</div>
								</div>
							<?php }?>
								<div id="show-map" class="vspan0">
									<div class="container-wrap">
										<div class="container">
											<div class="vspan3 border-bottom">
												<div id="table4" class="datagrid datagrid-single datagrid-selected no-loader" data-open="order"></div>
											</div>
											<div class="vspan7">
<input id="map-city-lat" type="hidden" value="41.549852" />
<input id="map-city-lon" type="hidden" value="60.631667" />
<input id="map-city-zoom" type="hidden" value="14" />
												<div class="container-fill" id="map" data-orders="false" data-drivers="true">
													<div class="ymaps-trafic hide">
														<div class="content">
															<b id="map-route-distance"></b>&nbsp;или&nbsp;<b id="map-route-time"></b>&nbsp;с учётом пробок<br>
															<span class="green">Стоимость:&nbsp;<b id="map-route-cost"></b>&nbsp;руб</span>
														</div>
													</div>
													<div class="ym-panel-cars ym-panel hide">
														<div class="content split">
															<div>ТС: <span id="CarsAll" style="font-weight: bold;">0</span></div>
															<div>Заказов: <span id="OrdersAll" style="font-weight: bold;">0</span></div>
														</div>	  
														<div class="content">
															<div class="row">
																<div class="span1">[<span id="CarsInviteP">0</span>%]</div>
																<div class="span2">Свободно</div>
																<div class="span3"><span id="CarsInvite" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsOrdersP">0</span>%]</div>
																<div class="span2">На заказе</div>
																<div class="span3"><span id="CarsOrders" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsBusyP">0</span>%]</div>
																<div class="span2">Занято</div>
																<div class="span3"><span id="CarsBusy" style="font-weight: bold;">0</span></div>
															</div>
															<div class="row">
																<div class="span1">[<span id="CarsNoGpsP">0</span>%]</div>
																<div class="span2">Нет GPS</div>
																<div class="span3"><span id="CarsNoGps" style="font-weight: bold;">0</span></div>
															</div>		
														</div>  
													</div>
												</div>
											</div>
										</div>
									</div>
								</div>
								<div id="show-chart" class="vspan0 hide">
									<div class="container-wrap container-inverse">
										<div class="container container-horizontal scroll-xx">
											<div class="hspan1_3p container-chart scroll-y border-right">
												<div id="chart3" class="chart300 container-white border-bottom"></div>
												<div class="chart-header border-bottom scroll-padding-q">
													<b>Принято заказов</b> <small>По дате создания заказа за указанный период.</small>
												</div>
												<ul id="chart3-detailng" class="chart-detailng scroll-padding-q"></ul>
											</div>
											<div class="hspan1_3p container-chart scroll-y border-right">
												<div id="chart1" class="chart300 container-white border-bottom"></div>
												<div class="chart-header border-bottom scroll-padding-q">
													<b>Выполнено заказов</b> <small>По дате подачи за указанный период.</small>
												</div>
												<ul id="chart1-detailng" class="chart-detailng scroll-padding-q"></ul>
											</div>
											<div class="hspan1_3p container-chart scroll-y border-right">
												<div id="chart2" class="chart300 container-white border-bottom"></div>
												<div class="chart-header border-bottom scroll-padding-q">
													<b>Типы заказов</b> <small>По типам заказов за указанный период.</small>
												</div>
												<ul id="chart2-detailng" class="chart-detailng scroll-padding-q"></ul>
											</div>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div id="container-right" class="container-nav container-nav-right hidden-phone">
			<div class="container-wrap">
				<div class="container">
					<div class="vspan0 container-nav-panel">
						<div class="container-wrap">
							<div class="container">
								<div class="vertical-stacked-small">
									<input class="input-block-level input-text" type="text" id="add-comment" disabled="disabled" placeholder="Написать сообщение" autocomplete="off" />
									<label class="checkbox split"><input settings="local" id="send-taximeter" type="checkbox" title="Отправить сообщение водителю на таксометр и SMS" />Водитель</label>
									<label class="checkbox"><input settings="local" id="send-sms-customer" type="checkbox" title="Отправить СМС клиенту" />Клиент</label>
								</div>
								<div id="item-messages" class="vspan0 chat chat-large scroll-y nonbounce"></div>
							</div>
						</div>
					</div>
				<?php if(!$access['disablePhoneInfo']){?>
					<div id="panel-phone-information" class="panel-phone-information container-nav-panel container-nav-panel-noborder">
						<div class="phone-number"></div>
						<div class="phone-status"></div>
					</div>
				<?php }?>
				<?php if(!$access['disableDriverInfo']){?>
					<div id="panel-driver-info" class="vspan90 container-nav-panel">
						<div class="container-wrap">
							<div class="container">
								<label class="header">Водитель</label>
								<div id="item-driver" class="vspan0 scroll-y scroll-text nonbounce"></div>
							</div>
						</div>
					</div>
				<?php }?>
				<?php if(!$access['disableDesc']){?>
					<div id="panel-description" class="vspan70 container-nav-panel container-nav-panel-noborder">
						<div class="container-wrap">
							<div class="container">
								<label class="header">Примечание</label>
								<div id="item-comment" class="vspan0 scroll-y scroll-text nonbounce"></div>
							</div>
						</div>
					</div>
				<?php }?>
				<?php if(!$access['disablePhone']){?>
					<div id="panel-phone">
						<div id="phone" class="phone" data-server="phone.avtolayn.uz">
							<div class="phone-expert-contanier modal-hide">
								<div class="modal-header">
									<button type="button" class="close phone-hide-expert">&times;</button>
									<h3>Настройки</h3>
								</div>
								<div class="modal-body">
									<table style="width: 100%">
										<tbody>
											<tr><td><label>Enable RTCWeb Breaker:</label></td><td><input type="checkbox" id="cbRTCWebBreaker"></td></tr>
											<tr><td><label>WebSocket Server URL:</label></td><td><input type="text" id="txtWebsocketServerUrl" value="wss://phone.avtolayn.uz:8089/ws" placeholder="e.g. ws://sipml5.org:5062"></td></tr>
											<tr><td><label>SIP outbound Proxy URL:</label></td><td><input type="text" id="txtSIPOutboundProxyUrl" value="" placeholder="e.g. udp://sipml5.org:5060"></td></tr>
											<tr><td><label>ICE Servers:</label></td><td><input type="text" id="txtIceServers" value="[{url:'stun:stun.l.google.com:19302'}]" placeholder="e.g. [{ url: 'stun:stun.l.google.com:19302'}, { url:'turn:user@numb.viagenie.ca', credential:'myPassword'}]"></td></tr>
											<tr><td><label>Max bandwidth (kbps):</label></td><td><input type="text" id="txtBandwidth" value="" placeholder="{ audio:64, video:512 }"></td></tr>
											<tr><td><label>Disable 3GPP Early IMS:</label></td><td><input type="checkbox" checked="checked" id="cbEarlyIMS"></td></tr>
											<tr><td><label>Cache the media stream:</label></td><td><input type="checkbox" checked="checked" id="cbCacheMediaStream"></td></tr>
										</tbody>
									</table>
								</div>
								<div class="modal-footer">
									<label id="txtInfo" style="position: absolute; left: 20px; bottom: 20px;"></label>
									<button type="button" class="btn btn-success" id="btnSave">Сохранить</button>
									<button type="button" class="btn btn-danger" id="btnRevert">Восстановить</button>
									<button class="btn phone-hide-expert" type="button">Закрыть</button>
								</div>
							</div>
							<div class="phone-modal-transfer modal hide">
								<div class="modal-header">
									<button type="button" class="close phone-hide-transfer">&times;</button>
									<h3>Перевести звонок</h3>
								</div>
								<div class="modal-body">
									<input type="text" class="transfer-number" maxlength="25" placeholder="Введите номер телефона" />
								</div>
								<div class="modal-footer">
									<button class="btn btn-default btn-default-primary phone-transfer-ok" type="button">OK</button>
									<button class="btn btn-default phone-hide-transfer" type="button">Закрыть</button>
								</div>
							</div>
							<div class="container-wrap">
								<div class="container phone-content">
									<ul class="nav nav-tabs">
										<li class="active"><a data-toggle="tab" class="phone-index" href="#phone-index">Телефон</a></li>
										<li><a data-toggle="tab" class="phone-journal" href="#phone-journal">Журнал</a></li>
										<li><a data-toggle="tab" class="phone-contacts" href="#phone-contacts">Контакты</a></li>
										<li><a data-toggle="tab" class="phone-settings" href="#phone-settings">Настройки</a></li>
									</ul>
									<div class="vspan0 tab-content">
										<div class="tab-pane active" id="phone-index">
											<div class="container-wrap">
												<div class="container">
													<div class="phone-dial">Входящая линия<span class="phone-dial-number"></span></div>
													<div class="vspan0">
														<div class="container-wrap">
															<input type="text" class="phone-number input-number" readonly="readonly" />
														</div>
													</div>
													<div class="phone-status"></div>
													<div class="container-wrap phone-buttons">
														<div class="phone-contanier-numbers">
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="1">1</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="2">2</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="3">3</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="4">4</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="5">5</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="6">6</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="7">7</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="8">8</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="9">9</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="*"><i class="star"></i></button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="0">0</button></div>
															<div class="btn-contanier"><button type="button" class="btn btn-default btn-default-color btn-default-gray" value="#">#</button></div>
														</div>

														<div class="phone-contanier-default">
															<div class="btn-contanier btn-contanier-two phone-btn-contanier-login">
																<button type="button" class="btn btn-default btn-default-color btn-default-gray small-size" value="login" disabled="disabled">Включить</button>
															</div>
															<div class="btn-contanier phone-btn-contanier-call hide">
																<button type="button" class="btn btn-default btn-default-color btn-default-green small-size" value="call">Вызов</button>
															</div>
															<div class="btn-contanier">
																<button type="button" class="btn btn-default btn-default-color btn-default-yellow" value="records" data-window="recordings"><i class="records"></i></button>
															</div>
															<div class="btn-contanier phone-btn-contanier-delete hide">
																<button type="button" class="btn btn-default btn-default-color btn-default-gray" value="delete"><i class="phone-delete"></i></button>
															</div>
														</div>
														<div class="phone-contanier-handup hide">
															<div class="btn-contanier btn-contanier-two">
																<button type="button" class="btn btn-default btn-default-color btn-default-yellow small-size" value="transfer">Transfer</button>
															</div>
															<div class="btn-contanier">
																<button type="button" class="btn btn-default btn-default-color btn-default-yellow small-size" value="hold">Hold</button>
															</div>
															<div class="btn-contanier btn-contanier-three">
																<button type="button" class="btn btn-default shotcut btn-default-color btn-default-red small-size" value="handup">Завершить <i>(F11)</i></button>
															</div>
														</div>
														<div class="phone-contanier-incall hide">
															<div class="btn-contanier btn-contanier-three">
																<button type="button" class="btn btn-default shotcut btn-default-color btn-default-green small-size" value="answer">Ответить <i>(F12)</i></button>
															</div>
															<div class="btn-contanier btn-contanier-three">
																<button type="button" class="btn btn-default shotcut btn-default-color btn-default-red small-size" value="handup">Завершить <i>(F11)</i></button>
															</div>
														</div>
													</div>
													<div class="container-wrap phone-buttons phone-contanier-line hide">
														<div class="btn-contanier">
															<button type="button" class="btn-line line1" data-line="1" value="line">линия 1</button>
														</div>
														<div class="btn-contanier">
															<button type="button" class="btn-line line2" data-line="2" value="line">линия 2</button>
														</div>
														<div class="btn-contanier">
															<button type="button" class="btn-line line3" data-line="3" value="line">линия 3</button>
														</div>
													</div>
												</div>
											</div>
										</div>
										<div class="tab-pane" id="phone-journal"></div>
										<div class="tab-pane" id="phone-contacts"></div>
										<div class="tab-pane" id="phone-settings">
											<div class="container-wrap">
												<div class="container">
													<div class="vspan0 scroll-y scroll-padding">
														<div class="phone-settings-row">
															<label>Логин:</label>
															<input type="text" class="input-login" value="201" />
														</div>
														<div class="phone-settings-row">
															<label>Пароль:</label>
															<input autocomplete="new-password" type="password" class="input-password"  value="201badpassword"  />
														</div>
														<div class="phone-settings-row">
															<label>SIP:</label>
															<input type="text" class="input-sip" value="sip:201@phone.avtolayn.uz" />
														</div>
													</div>
													<div class="phone-buttons">
														<div class="btn-contanier btn-contanier-three phone-show-expert-contanier">
															<button type="button" class="btn btn-default btn-default-color btn-default-yellow small-size phone-show-expert">Настройки</button>
														</div>
														<div class="phone-btn-contanier-logout btn-contanier btn-contanier-three hide">
															<button type="button" class="btn btn-default btn-default-color btn-default-red small-size"
																value="logout">Выключить</button>
														</div>
														<div class="phone-btn-contanier-login btn-contanier btn-contanier-three">
															<button type="button" class="btn btn-default btn-default-color btn-default-green small-size"
																value="login">Включить</button>
														</div>
													</div>
												</div>
											</div>
										</div>
									</div>
								</div>
							</div>
						</div>
						<audio id="audio_remote" autoplay="autoplay"></audio>
						<audio id="ringtone" loop="" src="assets/sounds/ringtone.wav"></audio>
						<audio id="ringbacktone" loop="" src="assets/sounds/ringbacktone.wav"></audio>
						<audio id="dtmfTone" src="assets/sounds/dtmf.wav"></audio>
					</div>
				<?php }?>
				</div>
			</div>
		</div>

<?php
include _FILE_(MODULES_PATH . "footer.php"); ?>
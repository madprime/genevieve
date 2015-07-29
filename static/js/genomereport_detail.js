var addIdData = function (b37ID, clinvarRelationsData, template, elem) {
  var varNameString = ''
  var varNames = []
  clinvarRelationsData.forEach(function (clinvarData) {
    var prefName = clinvarData['clinvar-rcva:preferred-name']
    if (!prefName) return

    if (varNameString) {
      // If this name already listed, don't output again.
      if (_.contains(varNames, prefName)) return
      varNameString = varNameString + '<br><small>or</small><br><b>' +
                      prefName + '</b>'
    } else {
      varNameString = '<b>' + clinvarData['clinvar-rcva:preferred-name']
    }
    varNames.push(prefName)
  })
  // console.log(varNames)
  var templated = template({
    clinvarRCVAPreferredName: varNameString,
    b37VariantID: b37ID
  })
  elem.append(templated)
  // console.log(elem)
  return [clinvarRelationsData[0]['clinvar-rcva:preferred-name'], b37ID]
}

var addFreqData = function (clinvarRelationsData, template, elem) {
  var frequencies = []
  clinvarRelationsData.forEach(function (clinvarData) {
    if ('clinvar-rcva:esp-allele-frequency' in clinvarData) {
      var freq = clinvarData['clinvar-rcva:esp-allele-frequency']
      if (_.contains(frequencies, freq)) return
      frequencies.push(freq)
    }
  })
  // console.log(frequencies)
  var frequency
  if (frequencies.length === 0) {
    frequency = 'Unknown'
  } else {
    frequency = frequencies[0]
  }
  var templated = template({clinvarRCVAfreqESP: frequency})
  elem.append(templated)
  // console.log(elem)
  return [frequency]
}

var addInfoData = function (clinvarRelationsData, template, elem) {
  var returnData = []
  clinvarRelationsData.forEach(
    function (clinvarData) {
      var traitType = clinvarData['clinvar-rcva:trait-type']
      var traitLabel
      if (traitType === 'Disease') {
        traitLabel = 'Disease'
      } else {
        traitLabel = 'Trait'
      }
      var templated = template({
        clinvarTraitLabel: traitLabel,
        clinvarRCVAAccession: clinvarData['clinvar-rcva:accession'],
        clinvarRCVADiseaseName: clinvarData['clinvar-rcva:trait-name'],
        clinvarRCVASignificance: clinvarData['clinvar-rcva:significance']
      })
      // console.log(templated)
      elem.append(templated)
      returnData.push([traitLabel, clinvarData['clinvar-rcva:accession'],
              clinvarData['clinvar-rcva:trait-name'],
              clinvarData['clinvar-rcva:significance']])
    }
  )
  // console.log(elem)
  return returnData
}

var asCSVContent = function (idData, freqData, infoData) {
  var csvContent = ''
  for (var i = 0; i < infoData.length; i++) {
    var infoDataItem = infoData[i]
    var data = idData.concat(freqData).concat(infoDataItem).map(function (e) {
      return '"' + e + '"'
    })
    csvContent += data.join(',') + '\n'
  }
  return csvContent
}

var addGennotesData = function (data, textStatus, jqXHR) {
  // Build a CSV version of the data for download.
  var csvContent = ''

  for (var i = 0; i < data['results'].length; i++) {
    var result = data['results'][i]
    // console.log(result['b37_id'])

    // Set up target elements by emptying them.
    var rowGV = $('tr#gv-' + result['b37_id'])
    var elemGVID = rowGV.find('td.gv-id-cell').empty()
    var elemGVFreq = rowGV.find('td.gv-freq-cell').empty()
    var elemGVInfo = rowGV.find('td.gv-info-cell').empty()

    // Load appropriate templates.
    var templateVariantID = _.template($('#variant-id-template').html())
    var templateVariantFreq = _.template($('#variant-freq-template').html())
    var templateVariantInfo = _.template($('#variant-info-template').html())

    // Extract list of Relations of type 'clinvar-rcva'.
    var clinvarRelationsData = []
    result['relation_set'].forEach(function (relation) {
      if (relation['tags']['type'] === 'clinvar-rcva') {
        clinvarRelationsData.push(relation['tags'])
      }
    })

    // No RCVA matches, prob variant was a multi-allele record - ignore it.
    if (clinvarRelationsData.length === 0) {
      rowGV.addClass('hidden')
      continue
    }

    // console.log('Adding ClinVar data')
    var idData = addIdData(result['b37_id'], clinvarRelationsData, templateVariantID, elemGVID)
    var freqData = addFreqData(clinvarRelationsData, templateVariantFreq, elemGVFreq)
    var infoData = addInfoData(clinvarRelationsData, templateVariantInfo, elemGVInfo)

    csvContent += asCSVContent(idData, freqData, infoData)
  }

  // Add CSV download link.
  // console.log("Adding CSV data as link:")
  // console.log(csvContent)
  var downloadCSVDiv = $('div#download-as-csv').empty()
  var downloadCSVLink = $('<a>Download as CSV file</a>')
    .attr('href', 'data:text/csv;charset=utf8,' + encodeURIComponent(csvContent))
    .attr('download', 'report.csv')
  downloadCSVDiv.append(downloadCSVLink)
}

$(function () {
  var variantList = $('tr.gv-row').map(function () {
    return $(this).attr('id').substring(3)
  }).toArray()
  // console.log(variantList)
  var variantListJSON = JSON.stringify(variantList)
  // console.log(variantListJSON)
  $.ajax(
    {
      url: 'http://gennotes.herokuapp.com/api/variant/',
      dataType: 'json',
      data: {'variant_list': variantListJSON, 'page_size': 100},
      success: addGennotesData
    }
  )
})
